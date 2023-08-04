"""Main server entry point."""
import argparse


def args():
    """Read commandline arguments."""
    parser = argparse.ArgumentParser(
        prog='pymscada',
        description='Connect IO, logic, applications and webpage UI.',
        epilog='Python MobileSCADA.'
    )
    parser.add_argument('component', type=str, help='bus, wwwserver, etc.')
    parser.add_argument('action', type=str, help='start, stop, restart')
    parser.add_argument('-c', '--config', metavar='config_file')
    return parser.parse_args()


def run():
    """Run bus and wwwserver."""
    print(args())
