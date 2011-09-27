from pecan.decorators    import transactional, after_commit
from pecan               import make_app, expose, request, redirect
from pecan.core          import state
from pecan.hooks         import PecanHook, TransactionHook, HookController, RequestViewerHook


def create_transactional_hook():
    run_hook = []
    @transactional()
    class RootController(object):
        
        @expose()
        def index(self):
            run_hook.append('inside')
            return 'Hello, World!'

        @expose()
        def redirect(self):
            redirect('/')
            
        @expose()
        @transactional(False)
        def redirect_rollback(self):
            redirect('/')

        @expose()
        def error(self):
            return [][1]

        @expose(generic=True)
        def generic(self):
            pass

        @generic.when(method='GET')
        def generic_get(self):
            run_hook.append('inside')
            return 'generic get'

        @generic.when(method='POST')
        def generic_post(self):
            run_hook.append('inside')
            return 'generic post'
    return run_hook, RootController
