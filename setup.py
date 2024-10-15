from setuptools import setup
from setuptools.command.install import install


class CustomInstallCommand(install):
    def run(self):
        install.run(self)
        print("\nInstallation complete!")
        print("Please run the following command to activate the environment:")
        print("source $(hms-utils-exports)\n")


setup(
    post_install_message="Thanks for installing my-package!",
    packages=["hms-utils"],
    cmdclass={
        "install": CustomInstallCommand
    }
)
