#!/usr/bin/env python
import os
import sys


def main():
    project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hoarder')
    sys.path.insert(0, project_root)
    os.chdir(project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hoarder.settings')

    import django
    django.setup()

    from django.core.management import call_command
    call_command('cleardatabase', *sys.argv[1:])


if __name__ == '__main__':
    main()
