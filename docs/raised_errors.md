# Raised Error Policy

Policy for exception types used in this project.

## Exception Types

**SystemExit**: Fatal errors where the program cannot continue safely (initialization errors, invalid state).

**SystemError**: Programming errors and internal errors indicating incorrect usage or bugs (recursion detection, callback errors).

**TypeError**: Type validation errors where data types are incorrect (protocol data type mismatches, function argument type validation).

**ValueError**: Valid types but invalid/missing values (e.g., required matrices absent, incompatible shapes passed as arguments before math is attempted).

**ArithmeticError**: Mathematical operation errors where operations cannot be performed (matrix shape mismatches, invalid matrix operations).

