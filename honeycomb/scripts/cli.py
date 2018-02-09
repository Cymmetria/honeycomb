from honeycomb import cli


def run_cli():
    cli.main(obj={}, auto_envvar_prefix="HC")  # all parameters will be taken from HC_PARAMETER first
