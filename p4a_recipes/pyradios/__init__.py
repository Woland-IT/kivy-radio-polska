from pythonforandroid.recipe import PythonRecipe

class PyradiosRecipe(PythonRecipe):
    version = '0.3.3'  # Poprawna, najnowsza wersja z PyPI
    url = 'https://files.pythonhosted.org/packages/source/p/pyradios/pyradios-{version}.tar.gz'
    depends = ['setuptools', 'requests']  # Dodaj requests, bo pyradios tego wymaga
    site_packages_name = 'pyradios'

recipe = PyradiosRecipe()