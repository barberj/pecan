import sys
import warnings
from paste.translogger import TransLogger
from webtest import TestApp

if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest  # noqa

from pecan import (
    Pecan, expose, request, response, redirect, abort, make_app,
    override_template, render
)
from pecan.templating import (
    _builtin_renderers as builtin_renderers, error_formatters
)
from pecan.decorators import accept_noncanonical

import os


class SampleRootController(object):
    pass


class TestAppRoot(unittest.TestCase):

    def test_controller_lookup_by_string_path(self):
        app = Pecan('pecan.tests.test_base.SampleRootController')
        assert app.root and isinstance(app.root, SampleRootController)


class TestIndexRouting(unittest.TestCase):

    @property
    def app_(self):
        class RootController(object):
            @expose()
            def index(self):
                return 'Hello, World!'

        return TestApp(Pecan(RootController()))

    def test_empty_root(self):
        r = self.app_.get('/')
        assert r.status_int == 200
        assert r.body == 'Hello, World!'

    def test_index(self):
        r = self.app_.get('/index')
        assert r.status_int == 200
        assert r.body == 'Hello, World!'

    def test_index_html(self):
        r = self.app_.get('/index.html')
        assert r.status_int == 200
        assert r.body == 'Hello, World!'


class TestObjectDispatch(unittest.TestCase):

    @property
    def app_(self):
        class SubSubController(object):
            @expose()
            def index(self):
                return '/sub/sub/'

            @expose()
            def deeper(self):
                return '/sub/sub/deeper'

        class SubController(object):
            @expose()
            def index(self):
                return '/sub/'

            @expose()
            def deeper(self):
                return '/sub/deeper'

            sub = SubSubController()

        class RootController(object):
            @expose()
            def index(self):
                return '/'

            @expose()
            def deeper(self):
                return '/deeper'

            sub = SubController()

        return TestApp(Pecan(RootController()))

    def test_index(self):
        r = self.app_.get('/')
        assert r.status_int == 200
        assert r.body == '/'

    def test_one_level(self):
        r = self.app_.get('/deeper')
        assert r.status_int == 200
        assert r.body == '/deeper'

    def test_one_level_with_trailing(self):
        r = self.app_.get('/sub/')
        assert r.status_int == 200
        assert r.body == '/sub/'

    def test_two_levels(self):
        r = self.app_.get('/sub/deeper')
        assert r.status_int == 200
        assert r.body == '/sub/deeper'

    def test_two_levels_with_trailing(self):
        r = self.app_.get('/sub/sub/')
        assert r.status_int == 200

    def test_three_levels(self):
        r = self.app_.get('/sub/sub/deeper')
        assert r.status_int == 200
        assert r.body == '/sub/sub/deeper'


class TestLookups(unittest.TestCase):

    @property
    def app_(self):
        class LookupController(object):
            def __init__(self, someID):
                self.someID = someID

            @expose()
            def index(self):
                return '/%s' % self.someID

            @expose()
            def name(self):
                return '/%s/name' % self.someID

        class RootController(object):
            @expose()
            def index(self):
                return '/'

            @expose()
            def _lookup(self, someID, *remainder):
                return LookupController(someID), remainder

        return TestApp(Pecan(RootController()))

    def test_index(self):
        r = self.app_.get('/')
        assert r.status_int == 200
        assert r.body == '/'

    def test_lookup(self):
        r = self.app_.get('/100/')
        assert r.status_int == 200
        assert r.body == '/100'

    def test_lookup_with_method(self):
        r = self.app_.get('/100/name')
        assert r.status_int == 200
        assert r.body == '/100/name'

    def test_lookup_with_wrong_argspec(self):
        class RootController(object):
            @expose()
            def _lookup(self, someID):
                return 'Bad arg spec'

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            app = TestApp(Pecan(RootController()))
            r = app.get('/foo/bar', expect_errors=True)
            assert r.status_int == 404


class TestControllerArguments(unittest.TestCase):

    @property
    def app_(self):
        class RootController(object):
            @expose()
            def index(self, id):
                return 'index: %s' % id

            @expose()
            def multiple(self, one, two):
                return 'multiple: %s, %s' % (one, two)

            @expose()
            def optional(self, id=None):
                return 'optional: %s' % str(id)

            @expose()
            def multiple_optional(self, one=None, two=None, three=None):
                return 'multiple_optional: %s, %s, %s' % (one, two, three)

            @expose()
            def variable_args(self, *args):
                return 'variable_args: %s' % ', '.join(args)

            @expose()
            def variable_kwargs(self, **kwargs):
                data = [
                    '%s=%s' % (key, kwargs[key])
                    for key in sorted(kwargs.keys())
                ]
                return 'variable_kwargs: %s' % ', '.join(data)

            @expose()
            def variable_all(self, *args, **kwargs):
                data = [
                    '%s=%s' % (key, kwargs[key])
                    for key in sorted(kwargs.keys())
                ]
                return 'variable_all: %s' % ', '.join(list(args) + data)

            @expose()
            def eater(self, id, dummy=None, *args, **kwargs):
                data = [
                    '%s=%s' % (key, kwargs[key])
                    for key in sorted(kwargs.keys())
                ]
                return 'eater: %s, %s, %s' % (
                    id,
                    dummy,
                    ', '.join(list(args) + data)
                )

            @expose()
            def _route(self, args):
                if hasattr(self, args[0]):
                    return getattr(self, args[0]), args[1:]
                else:
                    return self.index, args

        return TestApp(Pecan(RootController()))

    def test_required_argument(self):
        try:
            r = self.app_.get('/')
            assert r.status_int != 200
        except Exception, ex:
            assert type(ex) == TypeError
            assert ex.args[0] == 'index() takes exactly 2 arguments (1 given)'

    def test_single_argument(self):
        r = self.app_.get('/1')
        assert r.status_int == 200
        assert r.body == 'index: 1'

    def test_single_argument_with_encoded_url(self):
        r = self.app_.get('/This%20is%20a%20test%21')
        assert r.status_int == 200
        assert r.body == 'index: This is a test!'

    def test_two_arguments(self):
        r = self.app_.get('/1/dummy', status=404)
        assert r.status_int == 404

    def test_keyword_argument(self):
        r = self.app_.get('/?id=2')
        assert r.status_int == 200
        assert r.body == 'index: 2'

    def test_keyword_argument_with_encoded_url(self):
        r = self.app_.get('/?id=This%20is%20a%20test%21')
        assert r.status_int == 200
        assert r.body == 'index: This is a test!'

    def test_argument_and_keyword_argument(self):
        r = self.app_.get('/3?id=three')
        assert r.status_int == 200
        assert r.body == 'index: 3'

    def test_encoded_argument_and_keyword_argument(self):
        r = self.app_.get('/This%20is%20a%20test%21?id=three')
        assert r.status_int == 200
        assert r.body == 'index: This is a test!'

    def test_explicit_kwargs(self):
        r = self.app_.post('/', {'id': '4'})
        assert r.status_int == 200
        assert r.body == 'index: 4'

    def test_path_with_explicit_kwargs(self):
        r = self.app_.post('/4', {'id': 'four'})
        assert r.status_int == 200
        assert r.body == 'index: 4'

    def test_multiple_kwargs(self):
        r = self.app_.get('/?id=5&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'index: 5'

    def test_kwargs_from_root(self):
        r = self.app_.post('/', {'id': '6', 'dummy': 'dummy'})
        assert r.status_int == 200
        assert r.body == 'index: 6'

        # multiple args

    def test_multiple_positional_arguments(self):
        r = self.app_.get('/multiple/one/two')
        assert r.status_int == 200
        assert r.body == 'multiple: one, two'

    def test_multiple_positional_arguments_with_url_encode(self):
        r = self.app_.get('/multiple/One%20/Two%21')
        assert r.status_int == 200
        assert r.body == 'multiple: One , Two!'

    def test_multiple_positional_arguments_with_kwargs(self):
        r = self.app_.get('/multiple?one=three&two=four')
        assert r.status_int == 200
        assert r.body == 'multiple: three, four'

    def test_multiple_positional_arguments_with_url_encoded_kwargs(self):
        r = self.app_.get('/multiple?one=Three%20&two=Four%20%21')
        assert r.status_int == 200
        assert r.body == 'multiple: Three , Four !'

    def test_positional_args_with_dictionary_kwargs(self):
        r = self.app_.post('/multiple', {'one': 'five', 'two': 'six'})
        assert r.status_int == 200
        assert r.body == 'multiple: five, six'

    def test_positional_args_with_url_encoded_dictionary_kwargs(self):
        r = self.app_.post('/multiple', {'one': 'Five%20', 'two': 'Six%20%21'})
        assert r.status_int == 200
        assert r.body == 'multiple: Five%20, Six%20%21'

        # optional arg
    def test_optional_arg(self):
        r = self.app_.get('/optional')
        assert r.status_int == 200
        assert r.body == 'optional: None'

    def test_multiple_optional(self):
        r = self.app_.get('/optional/1')
        assert r.status_int == 200
        assert r.body == 'optional: 1'

    def test_multiple_optional_url_encoded(self):
        r = self.app_.get('/optional/Some%20Number')
        assert r.status_int == 200
        assert r.body == 'optional: Some Number'

    def test_multiple_optional_missing(self):
        r = self.app_.get('/optional/2/dummy', status=404)
        assert r.status_int == 404

    def test_multiple_with_kwargs(self):
        r = self.app_.get('/optional?id=2')
        assert r.status_int == 200
        assert r.body == 'optional: 2'

    def test_multiple_with_url_encoded_kwargs(self):
        r = self.app_.get('/optional?id=Some%20Number')
        assert r.status_int == 200
        assert r.body == 'optional: Some Number'

    def test_multiple_args_with_url_encoded_kwargs(self):
        r = self.app_.get('/optional/3?id=three')
        assert r.status_int == 200
        assert r.body == 'optional: 3'

    def test_url_encoded_positional_args(self):
        r = self.app_.get('/optional/Some%20Number?id=three')
        assert r.status_int == 200
        assert r.body == 'optional: Some Number'

    def test_optional_arg_with_kwargs(self):
        r = self.app_.post('/optional', {'id': '4'})
        assert r.status_int == 200
        assert r.body == 'optional: 4'

    def test_optional_arg_with_url_encoded_kwargs(self):
        r = self.app_.post('/optional', {'id': 'Some%20Number'})
        assert r.status_int == 200
        assert r.body == 'optional: Some%20Number'

    def test_multiple_positional_arguments_with_dictionary_kwargs(self):
        r = self.app_.post('/optional/5', {'id': 'five'})
        assert r.status_int == 200
        assert r.body == 'optional: 5'

    def test_multiple_positional_url_encoded_arguments_with_kwargs(self):
        r = self.app_.post('/optional/Some%20Number', {'id': 'five'})
        assert r.status_int == 200
        assert r.body == 'optional: Some Number'

    def test_optional_arg_with_multiple_kwargs(self):
        r = self.app_.get('/optional?id=6&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'optional: 6'

    def test_optional_arg_with_multiple_url_encoded_kwargs(self):
        r = self.app_.get('/optional?id=Some%20Number&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'optional: Some Number'

    def test_optional_arg_with_multiple_dictionary_kwargs(self):
        r = self.app_.post('/optional', {'id': '7', 'dummy': 'dummy'})
        assert r.status_int == 200
        assert r.body == 'optional: 7'

    def test_optional_arg_with_multiple_url_encoded_dictionary_kwargs(self):
        r = self.app_.post('/optional', {
            'id': 'Some%20Number',
            'dummy': 'dummy'
        })
        assert r.status_int == 200
        assert r.body == 'optional: Some%20Number'

        # multiple optional args

    def test_multiple_optional_positional_args(self):
        r = self.app_.get('/multiple_optional')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: None, None, None'

    def test_multiple_optional_positional_args_one_arg(self):
        r = self.app_.get('/multiple_optional/1')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, None, None'

    def test_multiple_optional_positional_args_one_url_encoded_arg(self):
        r = self.app_.get('/multiple_optional/One%21')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, None, None'

    def test_multiple_optional_positional_args_all_args(self):
        r = self.app_.get('/multiple_optional/1/2/3')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, 2, 3'

    def test_multiple_optional_positional_args_all_url_encoded_args(self):
        r = self.app_.get('/multiple_optional/One%21/Two%21/Three%21')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, Two!, Three!'

    def test_multiple_optional_positional_args_too_many_args(self):
        r = self.app_.get('/multiple_optional/1/2/3/dummy', status=404)
        assert r.status_int == 404

    def test_multiple_optional_positional_args_with_kwargs(self):
        r = self.app_.get('/multiple_optional?one=1')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, None, None'

    def test_multiple_optional_positional_args_with_url_encoded_kwargs(self):
        r = self.app_.get('/multiple_optional?one=One%21')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, None, None'

    def test_multiple_optional_positional_args_with_string_kwargs(self):
        r = self.app_.get('/multiple_optional/1?one=one')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, None, None'

    def test_multiple_optional_positional_args_with_encoded_str_kwargs(self):
        r = self.app_.get('/multiple_optional/One%21?one=one')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, None, None'

    def test_multiple_optional_positional_args_with_dict_kwargs(self):
        r = self.app_.post('/multiple_optional', {'one': '1'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, None, None'

    def test_multiple_optional_positional_args_with_encoded_dict_kwargs(self):
        r = self.app_.post('/multiple_optional', {'one': 'One%21'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One%21, None, None'

    def test_multiple_optional_positional_args_and_dict_kwargs(self):
        r = self.app_.post('/multiple_optional/1', {'one': 'one'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, None, None'

    def test_multiple_optional_encoded_positional_args_and_dict_kwargs(self):
        r = self.app_.post('/multiple_optional/One%21', {'one': 'one'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, None, None'

    def test_multiple_optional_args_with_multiple_kwargs(self):
        r = self.app_.get('/multiple_optional?one=1&two=2&three=3&four=4')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, 2, 3'

    def test_multiple_optional_args_with_multiple_encoded_kwargs(self):
        r = self.app_.get(
            '/multiple_optional?one=One%21&two=Two%21&three=Three%21&four=4'
        )
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One!, Two!, Three!'

    def test_multiple_optional_args_with_multiple_dict_kwargs(self):
        r = self.app_.post(
            '/multiple_optional',
            {'one': '1', 'two': '2', 'three': '3', 'four': '4'}
        )
        assert r.status_int == 200
        assert r.body == 'multiple_optional: 1, 2, 3'

    def test_multiple_optional_args_with_multiple_encoded_dict_kwargs(self):
        r = self.app_.post(
            '/multiple_optional',
            {
                'one': 'One%21',
                'two': 'Two%21',
                'three': 'Three%21',
                'four': '4'
            }
        )
        assert r.status_int == 200
        assert r.body == 'multiple_optional: One%21, Two%21, Three%21'

    def test_multiple_optional_args_with_last_kwarg(self):
        r = self.app_.get('/multiple_optional?three=3')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: None, None, 3'

    def test_multiple_optional_args_with_last_encoded_kwarg(self):
        r = self.app_.get('/multiple_optional?three=Three%21')
        assert r.status_int == 200
        assert r.body == 'multiple_optional: None, None, Three!'

    def test_multiple_optional_args_with_middle_arg(self):
        r = self.app_.get('/multiple_optional', {'two': '2'})
        assert r.status_int == 200
        assert r.body == 'multiple_optional: None, 2, None'

    def test_variable_args(self):
        r = self.app_.get('/variable_args')
        assert r.status_int == 200
        assert r.body == 'variable_args: '

    def test_multiple_variable_args(self):
        r = self.app_.get('/variable_args/1/dummy')
        assert r.status_int == 200
        assert r.body == 'variable_args: 1, dummy'

    def test_multiple_encoded_variable_args(self):
        r = self.app_.get('/variable_args/Testing%20One%20Two/Three%21')
        assert r.status_int == 200
        assert r.body == 'variable_args: Testing One Two, Three!'

    def test_variable_args_with_kwargs(self):
        r = self.app_.get('/variable_args?id=2&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'variable_args: '

    def test_variable_args_with_dict_kwargs(self):
        r = self.app_.post('/variable_args', {'id': '3', 'dummy': 'dummy'})
        assert r.status_int == 200
        assert r.body == 'variable_args: '

    def test_variable_kwargs(self):
        r = self.app_.get('/variable_kwargs')
        assert r.status_int == 200
        assert r.body == 'variable_kwargs: '

    def test_multiple_variable_kwargs(self):
        r = self.app_.get('/variable_kwargs/1/dummy', status=404)
        assert r.status_int == 404

    def test_multiple_variable_kwargs_with_explicit_kwargs(self):
        r = self.app_.get('/variable_kwargs?id=2&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'variable_kwargs: dummy=dummy, id=2'

    def test_multiple_variable_kwargs_with_explicit_encoded_kwargs(self):
        r = self.app_.get(
            '/variable_kwargs?id=Two%21&dummy=This%20is%20a%20test'
        )
        assert r.status_int == 200
        assert r.body == 'variable_kwargs: dummy=This is a test, id=Two!'

    def test_multiple_variable_kwargs_with_dict_kwargs(self):
        r = self.app_.post('/variable_kwargs', {'id': '3', 'dummy': 'dummy'})
        assert r.status_int == 200
        assert r.body == 'variable_kwargs: dummy=dummy, id=3'

    def test_multiple_variable_kwargs_with_encoded_dict_kwargs(self):
        r = self.app_.post(
            '/variable_kwargs',
            {'id': 'Three%21', 'dummy': 'This%20is%20a%20test'}
        )
        assert r.status_int == 200
        result = 'variable_kwargs: dummy=This%20is%20a%20test, id=Three%21'
        assert r.body == result

    def test_variable_all(self):
        r = self.app_.get('/variable_all')
        assert r.status_int == 200
        assert r.body == 'variable_all: '

    def test_variable_all_with_one_extra(self):
        r = self.app_.get('/variable_all/1')
        assert r.status_int == 200
        assert r.body == 'variable_all: 1'

    def test_variable_all_with_two_extras(self):
        r = self.app_.get('/variable_all/2/dummy')
        assert r.status_int == 200
        assert r.body == 'variable_all: 2, dummy'

    def test_variable_mixed(self):
        r = self.app_.get('/variable_all/3?month=1&day=12')
        assert r.status_int == 200
        assert r.body == 'variable_all: 3, day=12, month=1'

    def test_variable_mixed_explicit(self):
        r = self.app_.get('/variable_all/4?id=four&month=1&day=12')
        assert r.status_int == 200
        assert r.body == 'variable_all: 4, day=12, id=four, month=1'

    def test_variable_post(self):
        r = self.app_.post('/variable_all/5/dummy')
        assert r.status_int == 200
        assert r.body == 'variable_all: 5, dummy'

    def test_variable_post_with_kwargs(self):
        r = self.app_.post('/variable_all/6', {'month': '1', 'day': '12'})
        assert r.status_int == 200
        assert r.body == 'variable_all: 6, day=12, month=1'

    def test_variable_post_mixed(self):
        r = self.app_.post(
            '/variable_all/7',
            {'id': 'seven', 'month': '1', 'day': '12'}
        )
        assert r.status_int == 200
        assert r.body == 'variable_all: 7, day=12, id=seven, month=1'

    def test_no_remainder(self):
        try:
            r = self.app_.get('/eater')
            assert r.status_int != 200
        except Exception, ex:
            assert type(ex) == TypeError
            assert ex.args[0] == 'eater() takes at least 2 arguments (1 given)'

    def test_one_remainder(self):
        r = self.app_.get('/eater/1')
        assert r.status_int == 200
        assert r.body == 'eater: 1, None, '

    def test_two_remainders(self):
        r = self.app_.get('/eater/2/dummy')
        assert r.status_int == 200
        assert r.body == 'eater: 2, dummy, '

    def test_many_remainders(self):
        r = self.app_.get('/eater/3/dummy/foo/bar')
        assert r.status_int == 200
        assert r.body == 'eater: 3, dummy, foo, bar'

    def test_remainder_with_kwargs(self):
        r = self.app_.get('/eater/4?month=1&day=12')
        assert r.status_int == 200
        assert r.body == 'eater: 4, None, day=12, month=1'

    def test_remainder_with_many_kwargs(self):
        r = self.app_.get('/eater/5?id=five&month=1&day=12&dummy=dummy')
        assert r.status_int == 200
        assert r.body == 'eater: 5, dummy, day=12, month=1'

    def test_post_remainder(self):
        r = self.app_.post('/eater/6')
        assert r.status_int == 200
        assert r.body == 'eater: 6, None, '

    def test_post_three_remainders(self):
        r = self.app_.post('/eater/7/dummy')
        assert r.status_int == 200
        assert r.body == 'eater: 7, dummy, '

    def test_post_many_remainders(self):
        r = self.app_.post('/eater/8/dummy/foo/bar')
        assert r.status_int == 200
        assert r.body == 'eater: 8, dummy, foo, bar'

    def test_post_remainder_with_kwargs(self):
        r = self.app_.post('/eater/9', {'month': '1', 'day': '12'})
        assert r.status_int == 200
        assert r.body == 'eater: 9, None, day=12, month=1'

    def test_post_many_remainders_with_many_kwargs(self):
        r = self.app_.post(
            '/eater/10',
            {'id': 'ten', 'month': '1', 'day': '12', 'dummy': 'dummy'}
        )
        assert r.status_int == 200
        assert r.body == 'eater: 10, dummy, day=12, month=1'


class TestAbort(unittest.TestCase):

    def test_abort(self):
        class RootController(object):
            @expose()
            def index(self):
                abort(404)

        app = TestApp(Pecan(RootController()))
        r = app.get('/', status=404)
        assert r.status_int == 404

    def test_abort_with_detail(self):
        class RootController(object):
            @expose()
            def index(self):
                abort(status_code=401, detail='Not Authorized')

        app = TestApp(Pecan(RootController()))
        r = app.get('/', status=401)
        assert r.status_int == 401


class TestRedirect(unittest.TestCase):

    @property
    def app_(self):
        class RootController(object):
            @expose()
            def index(self):
                redirect('/testing')

            @expose()
            def internal(self):
                redirect('/testing', internal=True)

            @expose()
            def bad_internal(self):
                redirect('/testing', internal=True, code=301)

            @expose()
            def permanent(self):
                redirect('/testing', code=301)

            @expose()
            def testing(self):
                return 'it worked!'

        return TestApp(make_app(RootController(), debug=False))

    def test_index(self):
        r = self.app_.get('/')
        assert r.status_int == 302
        r = r.follow()
        assert r.status_int == 200
        assert r.body == 'it worked!'

    def test_internal(self):
        r = self.app_.get('/internal')
        assert r.status_int == 200
        assert r.body == 'it worked!'

    def test_internal_with_301(self):
        self.assertRaises(ValueError, self.app_.get, '/bad_internal')

    def test_permanent_redirect(self):
        r = self.app_.get('/permanent')
        assert r.status_int == 301
        r = r.follow()
        assert r.status_int == 200
        assert r.body == 'it worked!'

    def test_x_forward_proto(self):
        class ChildController(object):
            @expose()
            def index(self):
                redirect('/testing')

        class RootController(object):
            @expose()
            def index(self):
                redirect('/testing')

            @expose()
            def testing(self):
                return 'it worked!'
            child = ChildController()

        app = TestApp(make_app(RootController(), debug=True))
        res = app.get(
            '/child', extra_environ=dict(HTTP_X_FORWARDED_PROTO='https')
        )
        ##non-canonical url will redirect, so we won't get a 301
        assert res.status_int == 302
        ##should add trailing / and changes location to https
        assert res.location == 'https://localhost/child/'
        assert res.request.environ['HTTP_X_FORWARDED_PROTO'] == 'https'


class TestStreamedResponse(unittest.TestCase):

    def test_streaming_response(self):
        import StringIO

        class RootController(object):
            @expose(content_type='text/plain')
            def test(self, foo):
                if foo == 'stream':
                    # mimic large file
                    contents = StringIO.StringIO('stream')
                    response.content_type = 'application/octet-stream'
                    contents.seek(0, os.SEEK_END)
                    response.content_length = contents.tell()
                    contents.seek(0, os.SEEK_SET)
                    response.app_iter = contents
                    return response
                else:
                    return 'plain text'

        app = TestApp(Pecan(RootController()))
        r = app.get('/test/stream')
        assert r.content_type == 'application/octet-stream'
        assert r.body == 'stream'

        r = app.get('/test/plain')
        assert r.content_type == 'text/plain'
        assert r.body == 'plain text'


class TestStateCleanup(unittest.TestCase):

    def test_request_state_cleanup(self):
        """
        After a request, the state local() should be totally clean
        except for state.app (so that objects don't leak between requests)
        """
        from pecan.core import state

        class RootController(object):
            @expose()
            def index(self):
                return '/'

        app = TestApp(Pecan(RootController()))
        r = app.get('/')
        assert r.status_int == 200
        assert r.body == '/'

        assert state.__dict__.keys() == ['app']


class TestFileTypeExtensions(unittest.TestCase):

    @property
    def app_(self):
        """
        Test extension splits
        """
        class RootController(object):
            @expose(content_type=None)
            def _default(self, *args):
                return request.pecan['extension']

        return TestApp(Pecan(RootController()))

    def test_html_extension(self):
        r = self.app_.get('/index.html')
        assert r.status_int == 200
        assert r.body == '.html'

    def test_image_extension(self):
        r = self.app_.get('/image.png')
        assert r.status_int == 200
        assert r.body == '.png'

    def test_hidden_file(self):
        r = self.app_.get('/.vimrc')
        assert r.status_int == 200
        assert r.body == ''

    def test_multi_dot_extension(self):
        r = self.app_.get('/gradient.js.js')
        assert r.status_int == 200
        assert r.body == '.js'

    def test_bad_content_type(self):
        class RootController(object):
            @expose()
            def index(self):
                return '/'

        app = TestApp(Pecan(RootController()))
        r = app.get('/')
        assert r.status_int == 200
        assert r.body == '/'

        r = app.get('/index.html', expect_errors=True)
        assert r.status_int == 200
        assert r.body == '/'

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = app.get('/index.txt', expect_errors=True)
            assert r.status_int == 404


class TestCanonicalRouting(unittest.TestCase):

    @property
    def app_(self):
        class ArgSubController(object):
            @expose()
            def index(self, arg):
                return arg

        class AcceptController(object):
            @accept_noncanonical
            @expose()
            def index(self):
                return 'accept'

        class SubController(object):
            @expose()
            def index(self, **kw):
                return 'subindex'

        class RootController(object):
            @expose()
            def index(self):
                return 'index'

            sub = SubController()
            arg = ArgSubController()
            accept = AcceptController()

        return TestApp(Pecan(RootController()))

    def test_root(self):
        r = self.app_.get('/')
        assert r.status_int == 200
        assert 'index' in r.body

    def test_index(self):
        r = self.app_.get('/index')
        assert r.status_int == 200
        assert 'index' in r.body

    def test_broken_clients(self):
        # for broken clients
        r = self.app_.get('', status=302)
        assert r.status_int == 302
        assert r.location == 'http://localhost/'

    def test_sub_controller_with_trailing(self):
        r = self.app_.get('/sub/')
        assert r.status_int == 200
        assert 'subindex' in r.body

    def test_sub_controller_redirect(self):
        r = self.app_.get('/sub', status=302)
        assert r.status_int == 302
        assert r.location == 'http://localhost/sub/'

    def test_with_query_string(self):
        # try with query string
        r = self.app_.get('/sub?foo=bar', status=302)
        assert r.status_int == 302
        assert r.location == 'http://localhost/sub/?foo=bar'

    def test_posts_fail(self):
        try:
            self.app_.post('/sub', dict(foo=1))
            raise Exception("Post should fail")
        except Exception, e:
            assert isinstance(e, RuntimeError)

    def test_with_args(self):
        r = self.app_.get('/arg/index/foo')
        assert r.status_int == 200
        assert r.body == 'foo'

    def test_accept_noncanonical(self):
        r = self.app_.get('/accept/')
        assert r.status_int == 200
        assert 'accept' == r.body

    def test_accept_noncanonical_no_trailing_slash(self):
        r = self.app_.get('/accept')
        assert r.status_int == 200
        assert 'accept' == r.body


class TestNonCanonical(unittest.TestCase):

    @property
    def app_(self):
        class ArgSubController(object):
            @expose()
            def index(self, arg):
                return arg

        class AcceptController(object):
            @accept_noncanonical
            @expose()
            def index(self):
                return 'accept'

        class SubController(object):
            @expose()
            def index(self, **kw):
                return 'subindex'

        class RootController(object):
            @expose()
            def index(self):
                return 'index'

            sub = SubController()
            arg = ArgSubController()
            accept = AcceptController()

        return TestApp(Pecan(RootController(), force_canonical=False))

    def test_index(self):
        r = self.app_.get('/')
        assert r.status_int == 200
        assert 'index' in r.body

    def test_subcontroller(self):
        r = self.app_.get('/sub')
        assert r.status_int == 200
        assert 'subindex' in r.body

    def test_subcontroller_with_kwargs(self):
        r = self.app_.post('/sub', dict(foo=1))
        assert r.status_int == 200
        assert 'subindex' in r.body

    def test_sub_controller_with_trailing(self):
        r = self.app_.get('/sub/')
        assert r.status_int == 200
        assert 'subindex' in r.body

    def test_proxy(self):
        class RootController(object):
            @expose()
            def index(self):
                request.testing = True
                assert request.testing == True
                del request.testing
                assert hasattr(request, 'testing') == False
                return '/'

        app = TestApp(make_app(RootController(), debug=True))
        r = app.get('/')
        assert r.status_int == 200

    def test_app_wrap(self):
        class RootController(object):
            pass

        wrapped_apps = []

        def wrap(app):
            wrapped_apps.append(app)
            return app

        make_app(RootController(), wrap_app=wrap, debug=True)
        assert len(wrapped_apps) == 1


class TestLogging(unittest.TestCase):
    """
    Mocks logging calls so we can make sure they get called. We could use
    Fudge for this, but it would add an additional dependency to Pecan for
    a single set of tests.
    """

    def setUp(self):
        self._write_log = TransLogger.write_log

    def tearDown(self):
        TransLogger.write_log = self._write_log

    def test_default(self):

        class RootController(object):
            @expose()
            def index(self):
                return '/'

        # monkeypatch the logger
        writes = []

        def _write_log(self, *args, **kwargs):
            writes.append(1)
        TransLogger.write_log = _write_log

        # check the request
        app = TestApp(make_app(RootController(), debug=True))
        r = app.get('/')
        assert r.status_int == 200
        assert writes == []

    def test_default_route(self):

        class RootController(object):
            @expose()
            def index(self):
                return '/'

        # monkeypatch the logger
        writes = []

        def _write_log(self, *args, **kwargs):
            writes.append(1)
        TransLogger.write_log = _write_log

        # check the request
        app = TestApp(make_app(RootController(), debug=True))
        r = app.get('/')
        assert r.status_int == 200
        assert len(writes) == 0

    def test_no_logging(self):

        class RootController(object):
            @expose()
            def index(self):
                return '/'

        # monkeypatch the logger
        writes = []

        def _write_log(self, *args, **kwargs):
            writes.append(1)

        TransLogger.write_log = _write_log

        # check the request
        app = TestApp(make_app(RootController(), debug=True, logging=False))
        r = app.get('/')
        assert r.status_int == 200
        assert len(writes) == 0

    def test_basic_logging(self):

        class RootController(object):
            @expose()
            def index(self):
                return '/'

        # monkeypatch the logger
        writes = []

        def _write_log(self, *args, **kwargs):
            writes.append(1)

        TransLogger.write_log = _write_log

        # check the request
        app = TestApp(make_app(RootController(), debug=True, logging=True))
        r = app.get('/')
        assert r.status_int == 200
        assert len(writes) == 1

    def test_empty_config(self):

        class RootController(object):
            @expose()
            def index(self):
                return '/'

        # monkeypatch the logger
        writes = []

        def _write_log(self, *args, **kwargs):
            writes.append(1)

        TransLogger.write_log = _write_log

        # check the request
        app = TestApp(make_app(RootController(), debug=True, logging={}))
        r = app.get('/')
        assert r.status_int == 200
        assert len(writes) == 1

    def test_custom_config(self):

        class RootController(object):
            @expose()
            def index(self):
                return '/'

        # create a custom logger
        writes = []

        class FakeLogger(object):
            def log(self, *args, **kwargs):
                writes.append(1)

        # check the request
        app = TestApp(make_app(RootController(), debug=True,
                               logging={'logger': FakeLogger()}))
        r = app.get('/')
        assert r.status_int == 200
        assert len(writes) == 1


class TestEngines(unittest.TestCase):

    template_path = os.path.join(os.path.dirname(__file__), 'templates')

    @unittest.skipIf('genshi' not in builtin_renderers, 'Genshi not installed')
    def test_genshi(self):

        class RootController(object):
            @expose('genshi:genshi.html')
            def index(self, name='Jonathan'):
                return dict(name=name)

            @expose('genshi:genshi_bad.html')
            def badtemplate(self):
                return dict()

        app = TestApp(
            Pecan(RootController(), template_path=self.template_path)
        )
        r = app.get('/')
        assert r.status_int == 200
        assert "<h1>Hello, Jonathan!</h1>" in r.body

        r = app.get('/index.html?name=World')
        assert r.status_int == 200
        assert "<h1>Hello, World!</h1>" in r.body

        error_msg = None
        try:
            r = app.get('/badtemplate.html')
        except Exception, e:
            for error_f in error_formatters:
                error_msg = error_f(e)
                if error_msg:
                    break
        assert error_msg is not None

    @unittest.skipIf('kajiki' not in builtin_renderers, 'Kajiki not installed')
    def test_kajiki(self):

        class RootController(object):
            @expose('kajiki:kajiki.html')
            def index(self, name='Jonathan'):
                return dict(name=name)

        app = TestApp(
            Pecan(RootController(), template_path=self.template_path)
        )
        r = app.get('/')
        assert r.status_int == 200
        assert "<h1>Hello, Jonathan!</h1>" in r.body

        r = app.get('/index.html?name=World')
        assert r.status_int == 200
        assert "<h1>Hello, World!</h1>" in r.body

    @unittest.skipIf('jinja' not in builtin_renderers, 'Jinja not installed')
    def test_jinja(self):

        class RootController(object):
            @expose('jinja:jinja.html')
            def index(self, name='Jonathan'):
                return dict(name=name)

            @expose('jinja:jinja_bad.html')
            def badtemplate(self):
                return dict()

        app = TestApp(
            Pecan(RootController(), template_path=self.template_path)
        )
        r = app.get('/')
        assert r.status_int == 200
        assert "<h1>Hello, Jonathan!</h1>" in r.body

        error_msg = None
        try:
            r = app.get('/badtemplate.html')
        except Exception, e:
            for error_f in error_formatters:
                error_msg = error_f(e)
                if error_msg:
                    break
        assert error_msg is not None

    @unittest.skipIf('mako' not in builtin_renderers, 'Mako not installed')
    def test_mako(self):

        class RootController(object):
            @expose('mako:mako.html')
            def index(self, name='Jonathan'):
                return dict(name=name)

            @expose('mako:mako_bad.html')
            def badtemplate(self):
                return dict()

        app = TestApp(
            Pecan(RootController(), template_path=self.template_path)
        )
        r = app.get('/')
        assert r.status_int == 200
        assert "<h1>Hello, Jonathan!</h1>" in r.body

        r = app.get('/index.html?name=World')
        assert r.status_int == 200
        assert "<h1>Hello, World!</h1>" in r.body

        error_msg = None
        try:
            r = app.get('/badtemplate.html')
        except Exception, e:
            for error_f in error_formatters:
                error_msg = error_f(e)
                if error_msg:
                    break
        assert error_msg is not None

    def test_json(self):
        try:
            from simplejson import loads
        except:
            from json import loads  # noqa

        expected_result = dict(
            name='Jonathan',
            age=30, nested=dict(works=True)
        )

        class RootController(object):
            @expose('json')
            def index(self):
                return expected_result

        app = TestApp(Pecan(RootController()))
        r = app.get('/')
        assert r.status_int == 200
        result = dict(loads(r.body))
        assert result == expected_result

    def test_override_template(self):
        class RootController(object):
            @expose('foo.html')
            def index(self):
                override_template(None, content_type='text/plain')
                return 'Override'

        app = TestApp(Pecan(RootController()))
        r = app.get('/')
        assert r.status_int == 200
        assert 'Override' in r.body
        assert r.content_type == 'text/plain'

    def test_render(self):
        class RootController(object):
            @expose()
            def index(self, name='Jonathan'):
                return render('mako.html', dict(name=name))
                return dict(name=name)

        app = TestApp(
            Pecan(RootController(),
            template_path=self.template_path)
        )
        r = app.get('/')
        assert r.status_int == 200
        assert "<h1>Hello, Jonathan!</h1>" in r.body