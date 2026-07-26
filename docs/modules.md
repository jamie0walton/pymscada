# How Each Module Works

Read the help!
```bash
pymscada -h
pymscada module -h
```

## checkout

Creates the configuration folders and sets up so you can use systemd.
Provides tools to let you compare and change elements of the files.

Select and create a user for MobileSCADA.
Create a .venv, activate it and install pymscada.
This venv is detected by `checkout` for setting up systemd executables.
Create an empty folder for your configuration.
`cd` to the folder and create a `pymscada.md` file .

Minimally, and for _a single instance only_ you can:

```bash
source /my/python/.venv/bin/activate
cd /path/to/config
touch pymscada.md
pymscada checkout
```

Running `pymscada checkout --overwrite --site My_Site` will set the site
name while also **wiping** any custom edits. So do this early or manually
edit the service files.

## bus

Must run.

Runs the MobileSCADA tag value exchange bus. This is required. If it stops
ensure all client modules are stopped. systemd files are set to stop all
other modules when this happens.

```bash
su -
systemctl start ms-bus
```

## wwwserver

Runs the web server for the user interface. Required for init values for tags.

While the web server port can serve pages directly, preferred setup is to use
apache to provide user logins, gzip files, and generally interface to the wider
network.

