from templating         import RendererFactory
from routing            import lookup_controller, NonCanonicalPath
from util               import _cfg

from webob              import Request, Response, exc
from threading          import local
from itertools          import chain
from mimetypes          import guess_type

from formencode         import htmlfill, Invalid, variabledecode
from formencode.schema  import merge_dicts
from paste.recursive    import ForwardRequestException

try:
    from simplejson import loads
except ImportError: # pragma: no cover
    from json import loads

import os


state = local()


def proxy(key):
    class ObjectProxy(object):
        def __getattr__(self, attr):
            obj = getattr(state, key)
            return getattr(obj, attr)
        def __setattr__(self, attr, value):
            obj = getattr(state, key)
            return setattr(obj, attr, value)
        def __delattr__(self, attr):
            obj = getattr(state, key)
            return delattr(obj, attr)
    return ObjectProxy()


request     = proxy('request')
response    = proxy('response')


def override_template(template, content_type=None):
    request.pecan['override_template'] = template
    if content_type:
        request.pecan['override_content_type'] = content_type 

def abort(status_code=None, detail='', headers=None, comment=None):
    raise exc.status_map[status_code](detail=detail, headers=headers, comment=comment)


def redirect(location, internal=False, code=None, headers={}):
    if internal:
        if code is not None:
            raise ValueError('Cannot specify a code for internal redirects')
        raise ForwardRequestException(location)
    if code is None:
        code = 302
    raise exc.status_map[code](location=location, headers=getattr(response, 'headers', headers))


def error_for(field):
    return request.pecan['validation_errors'].get(field, '')


def static(name, value):
    if 'pecan.params' not in request.environ:
        request.environ['pecan.params'] = dict(request.str_params)    
    request.environ['pecan.params'][name] = value
    return value


def render(template, namespace):
    renderer = state.app.renderers.get(state.app.default_renderer, state.app.template_path)
    if template == 'json':
        renderer = state.app.renderers.get('json', state.app.template_path)
    else:
        namespace['error_for'] = error_for
        namespace['static'] = static
    if ':' in template:
        renderer = state.app.renderers.get(template.split(':')[0], state.app.template_path)
        template = template.split(':')[1]
    return renderer.render(template, namespace)


class ValidationException(ForwardRequestException):
    def __init__(self, location=None, errors={}):
        if hasattr(state, 'controller'):
            cfg = _cfg(state.controller)
        else:
            cfg = {}
        if location is None and 'error_handler' in cfg:
            location = cfg['error_handler']
            if callable(location):
                location = location()
        merge_dicts(request.pecan['validation_errors'], errors)
        if 'pecan.params' not in request.environ:
            request.environ['pecan.params'] = dict(request.str_params)
        request.environ['pecan.validation_errors'] = request.pecan['validation_errors']
        if cfg.get('htmlfill') is not None:
            request.environ['pecan.htmlfill'] = cfg['htmlfill']
        request.environ['REQUEST_METHOD'] = 'GET'
        ForwardRequestException.__init__(self, location)


class Pecan(object):
    def __init__(self, root, 
                 default_renderer    = 'mako', 
                 template_path       = 'templates', 
                 hooks               = [],
                 custom_renderers    = {},
                 extra_template_vars = {},
                 force_canonical     = True
                 ):

        self.root             = root
        self.renderers        = RendererFactory(custom_renderers, extra_template_vars)
        self.default_renderer = default_renderer
        self.hooks            = hooks
        self.template_path    = template_path
        self.force_canonical  = force_canonical
        
    def get_content_type(self, format):
        return guess_type(format)[0]
    
    def route(self, node, path):
        path = path.split('/')[1:]
        try:
            node, remainder = lookup_controller(node, path)
            return node, remainder
        except NonCanonicalPath, e:
            if self.force_canonical and not _cfg(e.controller).get('accept_noncanonical', False):
                if request.method == 'POST':
                    raise RuntimeError, "You have POSTed to a URL '%s' which '\
                        'requires a slash. Most browsers will not maintain '\
                        'POST data when redirected. Please update your code '\
                        'to POST to '%s/' or set force_canonical to False" % \
                        (request.pecan['routing_path'], request.pecan['routing_path'])
                raise exc.HTTPFound(add_slash=True)
            return e.controller, e.remainder
    
    def determine_hooks(self, controller=None):
        controller_hooks = []
        if controller:
            controller_hooks = _cfg(controller).get('hooks', [])
        return list(
            sorted(
                chain(controller_hooks, self.hooks), 
                lambda x,y: cmp(x.priority, y.priority)
            )
        )
    
    def handle_hooks(self, hook_type, *args):
        if hook_type in ['before', 'on_route']:
            hooks = state.hooks
        else:
            hooks = reversed(state.hooks)

        for hook in hooks:
             getattr(hook, hook_type)(*args)

    def get_args(self, all_params, remainder, argspec, im_self):
        args = []
        kwargs = dict()
        valid_args = argspec[0][1:]
        
        if im_self is not None:
            args.append(im_self)
        
        # grab the routing args from nested REST controllers
        if 'routing_args' in request.pecan:
            remainder = request.pecan['routing_args'] + list(remainder)
            del request.pecan['routing_args']
        
        # handle positional arguments
        if valid_args and remainder:
            args.extend(remainder[:len(valid_args)])
            remainder = remainder[len(valid_args):]
            valid_args = valid_args[len(args):]
        
        # handle wildcard arguments
        if remainder:
            if not argspec[1]:
                abort(404)
            args.extend(remainder)
        
        # get the default positional arguments
        if argspec[3]:
            defaults = dict(zip(argspec[0][-len(argspec[3]):], argspec[3]))
        else:
            defaults = dict()
        
        # handle positional GET/POST params
        for name in valid_args:
            if name in all_params:
                args.append(all_params.pop(name))
            elif name in defaults:
                args.append(defaults[name])
            else:
                break
        
        # handle wildcard GET/POST params
        if argspec[2]:
            for name, value in all_params.iteritems():
                if name not in argspec[0]:
                    kwargs[name] = value
        
        return args, kwargs
    
    def validate(self, schema, params, json=False, error_handler=None, 
                 htmlfill=None, variable_decode=None):
        try:
            to_validate = params
            if json:
                to_validate = loads(request.body)
            if variable_decode is not None:
                to_validate = variabledecode.variable_decode(to_validate, **variable_decode)
            params = schema.to_python(to_validate)
        except Invalid, e:
            kwargs = {}
            if variable_decode is not None:
                kwargs['encode_variables'] = True
                kwargs.update(variable_decode)
            request.pecan['validation_errors'] = e.unpack_errors(**kwargs)
            if error_handler is not None:
                raise ValidationException()
        if json:
            params = dict(data=params)
        return params
    
    def handle_request(self):
        
        # get a sorted list of hooks, by priority (no controller hooks yet)
        state.hooks = self.determine_hooks()
        
        # store the routing path to allow hooks to modify it
        request.pecan['routing_path'] = request.path

        # handle "on_route" hooks
        self.handle_hooks('on_route', state)
        
        # lookup the controller, respecting content-type as requested
        # by the file extension on the URI
        path = request.pecan['routing_path']

        if not request.pecan['content_type'] and '.' in path.split('/')[-1]:
            path, format = os.path.splitext(path)
            # store the extension for retrieval by controllers
            request.pecan['extension'] = format
            request.pecan['content_type'] = self.get_content_type(format)
        controller, remainder = self.route(self.root, path)
        cfg = _cfg(controller)

        if cfg.get('generic_handler'):
            raise exc.HTTPNotFound
        
        # handle generic controllers
        im_self = None
        if cfg.get('generic'):
            im_self = controller.im_self
            handlers = cfg['generic_handlers']
            controller = handlers.get(request.method, handlers['DEFAULT'])
            cfg = _cfg(controller)
                    
        # add the controller to the state so that hooks can use it
        state.controller = controller
    
        # if unsure ask the controller for the default content type 
        if not request.pecan['content_type']:
            request.pecan['content_type'] = cfg.get('content_type', 'text/html')
        elif cfg.get('content_type') is not None and \
            request.pecan['content_type'] not in cfg.get('content_types', {}):
            raise exc.HTTPNotFound
        
        # get a sorted list of hooks, by priority
        state.hooks = self.determine_hooks(controller)
    
        # handle "before" hooks
        self.handle_hooks('before', state)
        
        # fetch and validate any parameters
        params = dict(request.str_params)
        if 'schema' in cfg:
            params = self.validate(
                        cfg['schema'], 
                        params, 
                        json=cfg['validate_json'], 
                        error_handler=cfg.get('error_handler'), 
                        htmlfill=cfg.get('htmlfill'),
                        variable_decode=cfg.get('variable_decode')
                    )
        elif 'pecan.validation_errors' in request.environ:
            request.pecan['validation_errors'] = request.environ.pop('pecan.validation_errors')
        
        # fetch the arguments for the controller
        args, kwargs = self.get_args(
            params, 
            remainder,
            cfg['argspec'],
            im_self
        )
        
        # get the result from the controller
        result = controller(*args, **kwargs)

        # a controller can return the response object which means they've taken 
        # care of filling it out
        if result == response:
            return

        raw_namespace = result

        # pull the template out based upon content type and handle overrides
        template = cfg.get('content_types', {}).get(request.pecan['content_type'])

        # check if for controller override of template
        template = request.pecan.get('override_template', template)
        request.pecan['content_type'] = request.pecan.get('override_content_type', request.pecan['content_type'])

        # if there is a template, render it
        if template:
            if template == 'json':
                request.pecan['content_type'] = self.get_content_type('.json')
            result = render(template, result)
        
        # pass the response through htmlfill (items are popped out of the 
        # environment even if htmlfill won't run for proper cleanup)
        _htmlfill = cfg.get('htmlfill')
        if _htmlfill is None and 'pecan.htmlfill' in request.environ:
            _htmlfill = request.environ.pop('pecan.htmlfill')
        if 'pecan.params' in request.environ:
            params = request.environ.pop('pecan.params')
        if request.pecan['validation_errors'] and _htmlfill is not None and request.pecan['content_type'] == 'text/html':
            errors = request.pecan['validation_errors']
            result = htmlfill.render(result, defaults=params, errors=errors, **_htmlfill)
        
        # If we are in a test request put the namespace where it can be
        # accessed directly
        if request.environ.get('paste.testing'):
            testing_variables = request.environ['paste.testing_variables']
            testing_variables['namespace'] = raw_namespace
            testing_variables['template_name'] = template
            testing_variables['controller_output'] = result
        
        # set the body content
        if isinstance(result, unicode):
            response.unicode_body = result
        else:
            response.body = result
        
        # set the content type
        if request.pecan['content_type']:
            response.content_type = request.pecan['content_type']
    
    def __call__(self, environ, start_response):
        # create the request and response object
        state.request      = Request(environ)
        state.response     = Response()
        state.hooks        = []
        state.app          = self
        
        # handle the request
        try:
            # add context and environment to the request 
            state.request.context = {}
            state.request.pecan = dict(content_type=None, validation_errors={})

            self.handle_request()
        except Exception, e:
            # if this is an HTTP Exception, set it as the response
            if isinstance(e, exc.HTTPException):
                state.response = e
            
            # if this is not an internal redirect, run error hooks
            if not isinstance(e, ForwardRequestException):
                self.handle_hooks('on_error', state, e)
            
            if not isinstance(e, exc.HTTPException):
                raise
        finally:
            # handle "after" hooks
            self.handle_hooks('after', state)
            
        # get the response
        try:
            return state.response(environ, start_response)
        finally:        
            # clean up state
            del state.hooks
            del state.request
            del state.response
            if hasattr(state, 'controller'):
                del state.controller
