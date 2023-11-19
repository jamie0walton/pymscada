# Demo files

__ATTENTION__

Run ```pymscada checkout``` from the directory you want to have the
config folders and files automatically created.

## Config files

The config files are all in ```yaml``` format. These files are not used in
the demo. The original identical files from within the package are used
instead.

Edit these to suit your project, then update the
```pymscada-<module>.service``` file and recopy the service file to where
systemd uses it, then restart systemd and the service.

## Service files

The are also copies of the package files, however they are copied with
__DIR__, __EXE__ and __PYTHON__ re-written with values that make
sense from the folder __where you ran ```pymscada checkout```__.

## PDF files

A couple of demo pdf files are also copied in. These are served directly
by the wwwserver module for the component that pops up PDF files to view.
