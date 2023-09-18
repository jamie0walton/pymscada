# Build

## Initial creation

```
# Create the git repo online.
git clone https://github.com/jamie0walton/pymscada.git
# Open folder in vscode
pdm init
# venv -- yes
# installable library -- yes
# project name -- pymscada
# version -- 0.0.1
# description -- Shared tag value SCADA with python backup and Angular UI
# pdm-backend
# licence -- MIT
# Author Name -- Jamie Walton
# email -- jamie@walton.net.nz
# python -- >=3.9  although I am setting up in 3.11. importlib choice
pdm add -dG test pytest pytest-asyncio pytest-cov flake8 flake8-docstrings
pdm build
pdm sync  # this installs in editable mode which allows pytest to work
```

Dev
```
pymscada run bus --verbose
pymscada run wwwserver --config .\docs\examples\wwwserver.yaml --tags .\docs\examples\tags.yaml 
```