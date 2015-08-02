### Basic Handler + jinja template + user + cookie stuff

import os
import re
import random
import hashlib
import hmac
from string import letters
from collections import namedtuple

import webapp2
import jinja2

from google.appengine.ext import db


template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = False)

secret = 'TomMarvoloRiddle'


# Login (User) Stuff

def make_salt(length = 5):
    return ''.join(random.choice(letters) for x in xrange(length))

def make_pw_hash(name, pw, salt = ''):
    if not salt:
        salt = make_salt()
    return hashlib.sha256(name + pw + salt).hexdigest() + ',' + salt

def valid_pw(name, pw, h):
    salt = h.split(',')[1]
    return make_pw_hash(name, pw, salt) == h

def users_key(group = 'default'):
    return db.Key.from_path('users', group)
    
class User(db.Model):
    username = db.StringProperty(required = True)
    pw_hash = db.StringProperty(required = True)
    added_at = db.DateTimeProperty(auto_now_add = True)
    submitted_headlines = db.ListProperty(int)
    submitted_alternatives = db.ListProperty(int)
    upvoted_headlines = db.ListProperty(int)
    downvoted_headlines = db.ListProperty(int)
    upvoted_alt_headlines = db.ListProperty(int)

    @classmethod
    def by_id(cls, uid):
        return User.get_by_id(uid, parent = users_key())

    @classmethod
    def by_username(cls, username):
        u = User.all().filter('username =', username).get()
        return u

    @classmethod
    def register(cls, username, password):
        pw_hash = make_pw_hash(username, password)
        return User(parent = users_key(),
                    username = username,
                    pw_hash = pw_hash)

    @classmethod
    def login(cls, username, password):
        user = cls.by_username(username)
        if user and valid_pw(username, password, user.pw_hash):
            return user 

# Cookie functions

def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val

# Basic Handler + cookie stuff

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        params['user'] = self.user
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))

    @webapp2.cached_property
    def jinja2(self):
        return jinja2.get_jinja2(lambda app: jinja2.Jinja2(app=app,config={'environment_args':{'autoescape':False}}))

# Login Handler

class Login(Handler):
    def get(self):
        message_id = self.request.get('message_id')
        if message_id not in ['1', '2']:
            self.render('login.html')
        elif message_id == '1':
            self.render('login.html', message="You must log in to vote. If you don't have an account yet, please sign up!")
        elif message_id == '2':
            self.render('login.html', message="You must log in to submit. If you don't have an account yet, please sign up!")

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        user = User.login(username, password)
        if user:
            self.login(user)
            self.redirect('/')
        else:
            self.render('login.html', error = 'Oops, Seem\'s like a martian invasion distracted you from entering the right details.<br>Please try again!')

class Logout(Handler):
    def get(self):
        self.logout()
        self.redirect('/login')

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
    return username and USER_RE.match(username)

PASS_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
    return password and PASS_RE.match(password)

EMAIL_RE  = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
    return not email or EMAIL_RE.match(email)


# Signup Handler

class SignUp(Handler):
    def get(self):
        self.render("signup.html")

    def post(self):
        have_error = False
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')

        params = dict(username = self.username)

        if not valid_username(self.username):
            params['username_error'] = "That's not a valid username."
            have_error = True

        if not valid_password(self.password):
            params['password_error'] = "That wasn't a valid password."
            have_error = True
        elif self.password != self.verify:
            params['verify_error'] = "Your passwords didn't match."
            have_error = True

        if have_error:
            self.render('signup.html', **params)
        else:
            u = User.by_username(self.username)
            if u:
                self.render('signup.html', username_error = 'That user already exists!')
            else:
                u = User.register(self.username, self.password)
                u.put()
                print u
                self.login(u)
                self.redirect('/')



