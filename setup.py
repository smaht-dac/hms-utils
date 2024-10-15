from setuptools import setup
from setuptools.command.install import install


class CustomInstallCommand(install):
    def run(self):
        install.run(self)
        print("\nInstallation complete!")
        print("Please run the following command to activate the environment:")
        print("source path/to/myscript.sh\n")


setup(
    packages=["hms-utils"],
    cmdclass={
        "install": CustomInstallCommand
    }
)
