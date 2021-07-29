from setuptools import setup
from pkg_resources import parse_requirements


readme = open('README.md', 'r').read()


def get_requirements(filename: str) -> List[str]:
    with open(filename, 'rt') as f:
        text = f.read()
    requirements = [str(requirement) for requirement in parse_requirements(text)]
    return requirements


# https://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package
main_ns = {}
with open('subscriptions/__version__.py') as f:
    exec(f.read(), main_ns)

setup(
    version=main_ns['version'],
    long_description=readme,
    install_requires=required,
)