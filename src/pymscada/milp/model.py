"""Create and solve a MILP."""
import logging
import re
from datetime import datetime
from os import remove
from pathlib import Path
from subprocess import Popen, STDOUT, TimeoutExpired
from pymscada.milp.misc import as_list


def exact12(value, row: str='', col: str=''):
    """Return a float as 12 char string suitable for MPS format."""
    if value is None:
        return '            '
    if value > 10e10 or value < -10e10:
        logging.error(f"{value} MILP coefficient too big {row} {col}")
        sign = -1 if value < 0 else (1 if value > 0 else 0)
        value = sign * 10e10
    if value == 0.0:  # Pointless LOL
        return "0.0000000000"
    if abs(value) >= 0.001:
        simple = f"{value:.11f}"
        finddot = simple.find('.')
        if finddot == -1 or finddot < 11:
            return simple[:12]
    if value > 0:
        return f"{value:.6E}"
    else:
        return f"{value:.5E}"


class LpModel():
    """
    MILP model builder and runner.

    add_row     inequalities
    add_limit   BV and bounds - add rows first
    add_semi    semi-continuous, 0 or in range
    add_semi2   as above with a forbidden zone
    add_sos2    piecewise linear interpolation
    """

    def __init__(self, name=None, filename="tmp/__mpc", timeout=30):
        """Create MILP object to build and solve."""
        if name is None:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.name = f"MobileSCADA Model {now}"
        else:
            self.name = name
        self.rowno = 0
        self.colno = 0
        self.uniqueNo = 0
        self.rows = 5
        self.cols = 3
        self.model = [
            [0.0 for y in range(0, self.cols)]
            for x in range(0, self.rows)
        ]
        self.equality: list[str | None] = [None for x in range(0, self.rows)]
        self.RHS: list[float | None] = [0.0 for y in range(0, self.rows)]
        self.rowname = [f"R{x}" for x in range(self.rows)]
        self.colname = [f"C{x}" for x in range(self.cols)]
        self.bounds = {}
        self.binary = []
        self.resultdesc = ''
        self.solutioncost = None
        self.results = {}
        self.resultsdict = {}
        self.path = Path(filename)
        self.timeout = timeout
        self.found = False
        self.optimum = False
        self.resre = re.compile(rb'^C([0-9]+)\s+(\S+)$')
        logging.warning(f"LpModel __init__: {self.path.parent}")
        param = self.path.parent / f"{self.path.name}.param"
        lp = self.path.parent / f"{self.path.name}.lp"
        self._solver = ['/usr/local/bin/symphony', '-f', param, '-F', lp]

    def _increment_row_no(self):
        self.rowno += 1
        if self.rowno >= self.rows:
            self.rows += 1
            self.model.append([0.0 for y in range(0, self.cols)])
            self.equality.append(None)
            self.RHS.append(0.0)
            self.rowname.append(f"R{self.rowno}")
        pass

    def _increment_col_no(self):
        self.colno += 1
        if self.colno >= self.cols:
            self.cols += 1
            self.colname.append(f"C{self.colno}")
            for row in self.model:
                row.append(0.0)

    def get_unique_var(self, hint='', t=0):
        """Return a unique variable name for use in the MILP."""
        self.uniqueNo += 1
        return f"{hint}__Unique_{self.uniqueNo}__{t}"

    def _proc_line(self, line: bytes):
        if not self.found:
            if line.startswith(b'Preprocessing found the optimum'):
                self.resultdesc = 'found optimum in preprocessing'
                logging.warning("solve_mps Optimal Solution Found in Preprocessing")
                self.resultdesc
                self.found = True
                self.optimum = True
            elif line.startswith(b"* Optimal Solution Found"):
                self.resultdesc = 'found optimium'
                logging.warning("solve_mps Optimal Solution Found")
                self.found = True
                self.optimum = True
            elif line.startswith(
                    b"* Now displaying stats and best solution"):
                self.resultdesc = 'not found'
                logging.warning("solve_mps Non-optimal or no Solution")
                return
            elif line.startswith(b"* Problem Infeasible"):
                self.resultdesc = 'infeasible'
                logging.warning("solve_mps Problem Infeasible")
                return
            elif line.startswith(b"* Problem Found Infeasible"):
                self.resultdesc = 'infeasible'
                logging.warning("solve_mps Problem Infeasible in preproc")
                return
        elif not self.gotcost:
            if line.startswith(b"Solution Cost:"):
                self.solutioncost = float(line[15:])
                logging.warning(f"solve_mps got cost:{self.solutioncost}")
                self.gotcost = True
        elif self.gotcost:
            cline = self.resre.match(line)
            if cline is None:
                return
            col = self.colname[int(cline.group(1))]
            value = float(cline.group(2))
            self.results[col] = value

    def solve_mps(self):
        """
        Run a subprocess to solve the MILP.

        Uses the file prepared by write_mps. Parses output to self.result.
        """
        self.found = False
        self.optimum = False
        self.gotcost = False
        self.results = {}
        # symphony does not bother to return values of 0.0 so must initialise.
        for x in range(0, self.colno):
            self.results[self.colname[x]] = 0.0
        with open(self.path.parent / f"{self.path.name}.param", 'w') as pf:
            pf.write(f"time_limit {self.timeout}\n")

        # without newline='' messes up /r/n on Windows
        output_path = self.path.parent / f"{self.path.name}.output"
        with open(output_path, 'w+b') as of:
            with Popen(self._solver, stdout=of, stderr=STDOUT,
                       close_fds=True) as proc:
                try:
                    proc.communicate(timeout=self.timeout + 10)
                except TimeoutExpired:
                    logging.warning('model.py killing solver')
                    proc.kill()
                    proc.communicate()
            of.seek(0)
            output_text = of.read()
        for line in output_text.splitlines():
            self._proc_line(line)
                # for line in proc.stdout:
                #     self._proc_line(line)
                #     of.write(line)

        # has returned a -11 code after printing '* Optimal Solution Found'
        # so MUST unset found and optimum here.
        if proc.returncode != 0:
            logging.error(f'solve_mps failed, return code {proc.returncode}')
            self.found = False
            self.optimum = False
        if not self.found:
            logging.error('solve_mps No solution found')

    def parse_mps(self):
        """Convert raw results into a dictionary."""
        self.resultsdict = {}
        for name in self.results:
            if 'SLACK' in name and self.results[name] != 0:
                logging.warning(f"{name} is not zero {self.results[name]}")
            if name.startswith('_'):
                continue
            names = name.split('__')
            if len(names) != 3:
                continue
            if not names[0] in self.resultsdict:
                self.resultsdict[names[0]] = {}
            if not names[1] in self.resultsdict[names[0]]:
                self.resultsdict[names[0]][names[1]] = {}
            if not names[2] in self.resultsdict[names[0]][names[1]]:
                self.resultsdict[names[0]][names[1]][int(names[2])] = \
                    self.results[name]

    def remove_result(self):
        """Clean the working directory of result files."""
        for f in [
            self.path.parent / f"{self.path.name}.rows_cols",
            self.path.parent / f"{self.path.name}.debug",
            self.path.parent / f"{self.path.name}.lp",
            self.path.parent / f"{self.path.name}.yaml",
            self.path.parent / f"{self.path.name}.output",
            self.path.parent / f"{self.path.name}.param"
        ]:
            try:
                remove(f)
            except OSError:
                logging.warning(f"could not remove {f}")

    def _write_debug(self):
        f = open(self.path.parent / f"{self.path.name}.debug", 'w')
        for row in range(self.rowno):
            line = f"R{row}: "
            for col in range(self.colno):
                if self.model[row][col] == 0.0:
                    continue
                elif self.model[row][col] == 1.0:
                    if len(line) > 0:
                        line += f" + {self.colname[col]}"
                    else:
                        line += f"{self.colname[col]}"
                elif self.model[row][col] == -1.0:
                    line += f" - {self.colname[col]}"
                elif self.model[row][col] > 0.0:
                    line += f" + {self.model[row][col]} {self.colname[col]}"
                elif self.model[row][col] < 0.0:
                    line += f" - {- self.model[row][col]} {self.colname[col]}"
            if self.equality[row] == 'N':
                line = f"min: {line};\n"
            elif self.equality[row] == 'E':
                line += f" = {self.RHS[row]};\n"
            elif self.equality[row] == 'G':
                line += f" >= {self.RHS[row]};\n"
            elif self.equality[row] == 'L':
                line += f" <= {self.RHS[row]};\n"
            else:
                logging.error("Jamie missed something in the MPS debug write")
            f.write(line)
        f.close()

    def _write_rowscols(self):
        f = open(self.path.parent / f"{self.path.name}.rows_cols", 'w')
        for row in range(self.rowno):
            cols = []
            for col in range(self.colno):
                if self.model[row][col] != 0.0:
                    cols.append(self.colname[col])
            f.write(f"{self.rowname[row]}: {' '.join(cols)}\n")
        for col in range(self.colno):
            f.write(f"C{col}: {self.colname[col]}\n")
        f.close()

    def write_mps(self):
        """Write a MILP file in MPS format for the solver to read."""
        self._write_debug()
        self._write_rowscols()
        f = open(self._solver[len(self._solver) - 1], 'w')
        f.write(f"{'NAME':<11} {self.name:<60}\n")
        f.write('ROWS\n')
        [
            f.write(f" {self.equality[x]:<2} R{x:<11}\n")
            for x in range(0, self.rowno)
        ]
        f.write('COLUMNS\n')
        for col in range(self.colno):
            first = True  # for print per line
            for row in range(self.rowno):
                if self.model[row][col] != 0.0:
                    if first:
                        f.write(
                            f"    C{col:<7}"
                            f"  R{row:<7}"
                            f"  {exact12(self.model[row][col])}"
                        )
                    else:
                        f.write(
                            f"   R{row:<7}"
                            f"  {exact12(self.model[row][col])}\n"
                        )
                    first = not first
            if not first:
                f.write("\n")
        f.write('RHS\n')
        first = True  # for print per line
        for row in range(self.rowno):
            if self.equality[row] == 'N':  # no RHS for objective
                continue
            if first:
                f.write(
                    f"    RHS       {self.rowname[row]:<8}"
                    f"  {exact12(self.RHS[row])}"
                )
            else:
                f.write(
                    f"   {self.rowname[row]:<8}"
                    f"  {exact12(self.RHS[row])}\n"
                )
            first = not first
        if not first:
            f.write('\n')
        f.write('BOUNDS\n')
        for col, bnd in self.bounds.items():
            f.write(
                f" {bnd['type']:<2} {'BOUND':<8}"
                f"  C{col:<7}"
                f"  {exact12(bnd['value'])}\n"
            )
        f.write('ENDATA\n')
        f.close()

    def add_semi(
        self, free: str, min_: float, max_: float,
        running_bv: str | None = None
    ):
        """
        Add semi continuous constraint, 0, [min, max].

        Good for generators, solution allows results
        of 0 and between min and max.

        Return the Binary to allow other conditions to be
        added externally (max changes in a time period)
        """
        if running_bv is None:
            running_bv = self.get_unique_var('_BV')
        self.add_row(min_, running_bv, -1, free, 'L', 0)
        self.add_row(-max_, running_bv, 1, free, 'L', 0)
        self.add_limit(running_bv, 'BV', None)
        return (running_bv, None)

    def add_semi2(
        self, free: str, min1: float, max1: float, min2: float, max2: float,
        running_bv: str | None = None, range_bv: str | None = None
    ):
        """
        Good for generators, solution has two forbidden zones.

        Return the Binary to allow other conditions to be added externally
        (max changes in a time period)
        """
        if running_bv is None:
            running_bv = self.get_unique_var('_BV')
        if range_bv is None:
            range_bv = self.get_unique_var('_BV')
        # Both approaches work but this is better for binvar meaning
        # binvar1 is on / off, binvar2 is between ranges
        self.add_row(min1, running_bv, (min2 - min1), range_bv, -1, free,
                     'L', 0)
        self.add_row(max1, running_bv, (max2 - max1), range_bv, -1, free,
                     'G', 0)
        self.add_row(running_bv, -1.0, range_bv, 'G', 0)
        # self.add_row(min1, running_bv, min2, range_bv, -1, free, 'L', 0)
        # self.add_row(-max1, running_bv, -max2, range_bv, 1, free, 'L', 0)
        # self.add_row(running_bv, range_bv, 'L', 1)
        self.add_limit(running_bv, 'BV', None)
        self.add_limit(range_bv, 'BV', None)
        return (running_bv, range_bv)

    def add_range2(self, free: str, min1: float, max1: float, min2: float,
                   max2: float, range_bv: str | None = None):
        """
        Good for generators, solution allows results of between min and max.

        Return the Binary to allow other conditions to be added externally
        (max changes in a time period)
        """
        if range_bv is None:
            range_bv = self.get_unique_var('_BV')
        self.add_row((min2 - min1), range_bv, -1, free, 'L', -min1)
        self.add_row((max2 - max1), range_bv, -1, free, 'G', -max1)
        # self.add_row(min1, binvar1, min2, range_bv, -1, free, 'L', 0)
        # self.add_row(-max1, binvar1, -max2, range_bv, 1, free, 'L', 0)
        # self.add_row(binvar1, range_bv, 'E', 1)
        # self.add_limit(binvar1, 'BV', None)
        self.add_limit(range_bv, 'BV', None)
        return (None, range_bv)

    def add_sos2(self, xname: str, xval, yname: str, yval):
        """Piecewise linear interpolation."""
        if len(xval) != len(yval):
            logging.error(f"SOS2 {xval} and {yval} arrays invalid")
            return
        # create auxiliary variables
        s = []  # fraction through range
        z = []  # active range
        for i in range(len(xval) - 1):
            z.append(self.get_unique_var(f"_Z{i}_{xname}"))
            s.append(self.get_unique_var(f"_S{i}_{xname}"))
        for i in range(len(s)):
            self.add_limit(z[i], 'BV', None)  # 1 if active in range
            self.add_row(1, s[i], -1, z[i], 'L', 0)  # if inactive, forced to 0
        self.add_row(z, 'E', 1)  # only one range can be active
        # create the piecewise linear conditions
        x = []
        y = []
        for i in range(len(xval) - 1):
            # accumulate the piecewise ranges
            x.append([xval[i], z[i], xval[i + 1] - xval[i], s[i]])
            y.append([yval[i], z[i], yval[i + 1] - yval[i], s[i]])
        # as only one range can be active this ties xname and yname
        self.add_row(x, -1, xname, 'E', 0)
        self.add_row(y, -1, yname, 'E', 0)

    def add_sos2_disc(self, xname: str, xval, yname: str, yval):
        """Piecewise linear interpolation limit for discontinuous ranges."""
        if len(xval) - 1 != len(yval):
            logging.error(f"SOS2 discontinuous {xval} and {yval} arrays invalid")
            return
        # create auxiliary variables
        s = []  # fraction through range
        z = []  # active range
        for i in range(len(xval) - 1):
            z.append(self.get_unique_var(f"_Z{i}_{xname}"))
            s.append(self.get_unique_var(f"_S{i}_{xname}"))
        for i in range(len(s)):
            self.add_limit(z[i], 'BV', None)  # 1 if active in range
            self.add_row(1, s[i], -1, z[i], 'L', 0)  # if inactive, forced to 0
        self.add_row(z, 'E', 1)  # only one range can be active
        # create the piecewise linear conditions
        x = []
        y = []
        for i in range(len(xval) - 1):
            # accumulate the piecewise ranges
            x.append([xval[i], z[i], xval[i + 1] - xval[i], s[i]])
            y.append([yval[i][0], z[i], yval[i][1] - yval[i][0], s[i]])
        # as only one range can be active this ties xname and yname
        self.add_row(x, -1, xname, 'E', 0)
        self.add_row(y, -1, yname, 'E', 0)

    def add_limit(self, var: str, limtype: str, value: float | None = None):
        """
        Add a MILP Limit constraint.

                type            meaning
        ---------------------------------------------------
            LO    lower bound        b <= x (< +inf)
            UP    upper bound        (0 <=) x <= b
            FX    fixed variable     x = b
            FR    free variable      -inf < x < +inf
            MI    lower bound -inf   -inf < x (<= 0)
            PL    upper bound +inf   (0 <=) x < +inf
            BV    binary variable    x = 0 or 1
            LI    integer variable   b <= x (< +inf)
            UI    integer variable   (0 <=) x <= b
            SC    semi-cont variable x = 0 or l <= x <= b
                l is the lower bound on the variable
                If none set then defaults to 1
        """
        try:
            colno = self.colname.index(var)
        except ValueError:
            colno = self.colno
            self.colname[self.colno] = var
            self._increment_col_no()
        if colno in self.bounds:
            if self.bounds[colno]['type'] == limtype and \
                    self.bounds[colno]['type'] == value:
                logging.critical(f"{var} bounds changed {limtype} {value}")
        else:
            self.bounds[colno] = {"var": var, "type": limtype, "value": value}

    def add_between(self, xname: str, aname: str, bname: str):
        """Either lim1 < x < lim2 or lim1 > x > lim2."""
        z = self.get_unique_var(f"_aGTb_{xname}")
        y = self.get_unique_var(f"_aLTb_{xname}")
        self.add_limit(z, 'BV', None)
        self.add_limit(y, 'BV', None)
        self.add_row(z, y, 'E', 1)
        self.add_row(xname, -1, aname, 1000000, z, 'G', 0)
        self.add_row(xname, -1, aname, -1000000, y, 'L', 0)
        self.add_row(xname, -1, bname, 1000000, y, 'G', 0)
        self.add_row(xname, -1, bname, -1000000, z, 'L', 0)

    def add_row(self, *args):
        """
        Add a MILP row.

                type      meaning
        ---------------------------
        E    equality
        L    less than or equal
        G    greater than or equal
        N    objective
        N    no restriction - Don't use this
        """
        try:
            row: list = as_list(*args)
        except ValueError as e:
            raise ValueError(f"{e} parsing {args}")
        last = row.pop()
        if type(last) == str:
            self.equality[self.rowno] = 'N'
            self.RHS[self.rowno] = None
        else:  # if type(last) == float or type(last) == int:
            self.equality[self.rowno] = row.pop()
            self.RHS[self.rowno] = last
        coeff = 1.0
        for var in row:
            if type(var) == str:
                if var not in self.colname:
                    self.colname[self.colno] = var
                    self._increment_col_no()
                varcol = self.colname.index(var)
                self.model[self.rowno][varcol] = coeff
                coeff = 1.0
            else:
                coeff = var
                if abs(coeff) > 1e9:
                    logging.warning(f"Coeff hi in {args}")
        self._increment_row_no()
