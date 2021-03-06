.. _quick_start:

Creating Your First Pecan Application
=====================================

Let's create a small sample project with Pecan.

.. note::
    This guide does not cover the installation of Pecan. If you need
    instructions for installing Pecan, go to :ref:`installation`.


Base Application Template
-------------------------

A basic template for getting started is included with Pecan.  From
your shell, type::

    $ pecan create test_project

This example uses *test_project* as your project name, but you can replace
it with any valid Python package name you like.

Go ahead and change into your newly created project directory::

    $ cd test_project
    $ ls

This is how the layout of your new project should look::

    ├── MANIFEST.in
    ├── config.py
    ├── public
    │   ├── css
    │   │   └── style.css
    │   └── images
    ├── setup.cfg
    ├── setup.py
    └── test_project
        ├── __init__.py
        ├── app.py
        ├── controllers
        │   ├── __init__.py
        │   └── root.py
        ├── model
        │   └── __init__.py
        ├── templates
        │   ├── error.html
        │   ├── index.html
        │   └── layout.html
        └── tests
            ├── __init__.py
            ├── config.py
            ├── test_functional.py
            └── test_units.py

The amount of files and directories may vary, but the above structure should
give you an idea of what you should expect.

A few things have been created for you, so let's review them one by one:

* **public**: All your static files (like CSS, Javascript, and images) live
  here.  Pecan comes with a simple file server that serves these static files
  as you develop.


Pecan application structure generally follows the
`MVC <http://en.wikipedia.org/wiki/Model–view–controller>`_ pattern.  The
remaining directories encompass your models, controllers and templates...

*  **test_project/controllers**:  The container directory for your controller files.
*  **test_project/templates**:    All your templates go in here.
*  **test_project/model**:        Container for your model files.

...and finally, a directory to house unit and integration tests:

*  **test_project/tests**:        All of the tests for your application.

To avoid unneeded dependencies and to remain as flexible as possible, Pecan
doesn't impose any database or ORM 
(`Object Relational Mapper
<http://en.wikipedia.org/wiki/Object-relational_mapping>`_) out of the box.
You may notice that **model/__init__.py** is mostly empty.  If your project
will interact with a database, this if where you should add code to parse
bindings from your configuration file and define tables and ORM definitions.

Now that you've created your first Pecan application, you'll want to deploy it
in "development mode", such that it’s available on ``sys.path``, yet can still
be edited directly from its source distribution::

    $ python setup.py develop

.. _running_application:

Running the Application
-----------------------
Before starting up your Pecan app, you'll need a configuration file.  The
base project template should have created one for you already, ``config.py``.

This file already contains the basic necessary information to run your Pecan
app, like the host and port to serve it on, where your controllers and templates
are stored on disk, and which directory to serve static files from.

If you just run ``pecan serve``, passing ``config.py`` as an argument for
configuration, it will bring up the development server and serve the app::

    $ pecan serve config.py 
    Starting server in PID 000.
    serving on 0.0.0.0:8080, view at http://127.0.0.1:8080

The location for the configuration file and the argument itself are very
flexible - you can pass an absolute or relative path to the file.


Python-Based Configuration
--------------------------
For ease of use, Pecan configuration files are pure Python - they're even saved
as ``.py`` files.

This is how your default (generated) configuration file should look::

    # Server Specific Configurations
    server = {
        'port': '8080',
        'host': '0.0.0.0'
    }

    # Pecan Application Configurations
    app = {
        'root': '${package}.controllers.root.RootController',
        'modules': ['${package}'],
        'static_root': '%(confdir)s/public', 
        'template_path': '%(confdir)s/${package}/templates',
        'debug': True,
        'errors': {
            '404': '/error/404',
            '__force_dict__': True
        }
    }

    logging = {
        'loggers': {
            'root' : {'level': 'INFO', 'handlers': ['console']},
            '${package}': {'level': 'DEBUG', 'handlers': ['console']}
        },
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'simple'
            }
        },
        'formatters': {
            'simple': {
                'format': ('%(asctime)s %(levelname)-5.5s [%(name)s]'
                           '[%(threadName)s] %(message)s')
            }
        }
    }

    # Custom Configurations must be in Python dictionary format::
    #
    # foo = {'bar':'baz'}
    #
    # All configurations are accessible at::
    # pecan.conf

You can also add your own configuration as Python dictionaries.

There's a lot to cover here, so we'll come back to configuration files in
a later chapter (:ref:`Configuration`).

    
The Application Root
--------------------
The **Root Controller** is the root of your application.  You can think of it
as being analogous to your application's root path (in our case,
``http://localhost:8080/``).

This is how it looks in the project template
(``test_project.controllers.root.RootController``)::

    from pecan import expose
    from webob.exc import status_map


    class RootController(object):

        @expose(generic=True, template='index.html')
        def index(self):
            return dict()

        @index.when(method='POST')
        def index_post(self, q):
            redirect('http://pecan.readthedocs.org/en/latest/search.html?q=%s' % q)

        @expose('error.html')
        def error(self, status):
            try:
                status = int(status)
            except ValueError:
                status = 0
            message = getattr(status_map.get(status), 'explanation', '')
            return dict(status=status, message=message)


You can specify additional classes and methods if you need to do so, but for 
now, let's examine the sample project, controller by controller::

    @expose(generic=True, template='index.html')
    def index(self):
        return dict()

The ``index`` method is marked as **publically available** via the ``@expose`` 
decorator (which in turn uses the ``index.html`` template) at the root of the
application (http://127.0.0.1:8080/), so any HTTP ``GET`` that hits the root of
your application (``/``) will be routed to this method.

Notice that the ``index`` method returns a Python dictionary - this dictionary
is used as a namespace to render the specified template (``index.html``) into
HTML, and is the primary mechanism by which data is passed from controller to 
template.

::

    @index.when(method='POST')
    def index_post(self, q):
        redirect('http://pecan.readthedocs.org/en/latest/search.html?q=%s' % q)

The ``index_post`` method receives one HTTP ``POST`` argument (``q``).  Because
the argument ``method`` to ``@index.when`` has been set to ``'POST'``, any
HTTP ``POST`` to the application root (in the example project, a form
submission) will be routed to this method.

::

    @expose('error.html')
    def error(self, status):
        try:
            status = int(status)
        except ValueError:
            status = 0
        message = getattr(status_map.get(status), 'explanation', '')
        return dict(status=status, message=message)

Finally, we have the ``error`` method, which allows the application to display
custom pages for certain HTTP errors (``404``, etc...).

Running the Tests For Your Application
--------------------------------------
Your application comes with a few example tests that you can run, replace, and
add to.  To run them::

    $ python setup.py test -q
    running test
    running egg_info
    writing requirements to sam.egg-info/requires.txt
    writing sam.egg-info/PKG-INFO
    writing top-level names to sam.egg-info/top_level.txt
    writing dependency_links to sam.egg-info/dependency_links.txt
    reading manifest file 'sam.egg-info/SOURCES.txt'
    reading manifest template 'MANIFEST.in'
    writing manifest file 'sam.egg-info/SOURCES.txt'
    running build_ext
    ....
    ----------------------------------------------------------------------
    Ran 4 tests in 0.009s

    OK

The tests themselves can be found in the ``tests`` module in your project.
