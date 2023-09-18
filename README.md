# pymscada
A simple bus and shared value SCADA system with an angular html client


# Quick Start

```
pip install pymscada
```

In separate windows:
```
pymscada run bus
pymscada run wwwserver --config .\docs\examples\wwwserver.yaml --tags .\docs\examples\tags.yaml
pymscada run files --config .\docs\examples\files.yaml
http://localhost:8324
```
