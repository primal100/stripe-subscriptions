from setuptools import setup


# https://stackoverflow.com/questions/2058802/how-can-i-get-the-version-defined-in-setup-py-setuptools-in-my-package
main_ns = {}
with open('subscriptions/__version__.py') as f:
    exec(f.read(), main_ns)

setup(
    version=main_ns['version'],
)