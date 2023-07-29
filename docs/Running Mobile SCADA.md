# Running

## Debian

With PEP668 things are now a little more complicated. I suggest you use a
package management tool that also looks after virtual environments.

Create your package for your instance of MobileSCADA. ```pdm add pymscada```
then create your config files, see the 
[examples](https://github.com/jamie0walton/pymscada/tree/main/docs/examples).
Probably best to do a one for one copy to begin with and see that you can
get a web page up and running. After that its easier.

You may need to run pymscada with the --verbose tag so that you can see the
errors. The yaml files need a schema checker and I've not written one.
