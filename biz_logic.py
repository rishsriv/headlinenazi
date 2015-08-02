### theAfterSales

import basic

import logging
import datetime

import webapp2
from google.appengine.ext import db
from google.appengine.api import memcache

# Database Objects
class Headline(db.Model):
	headline = db.TextProperty(required=True)
	submitted_by = db.IntegerProperty(required=True)
	link_to_headline = db.StringProperty(required=False)
	comments = db.StringProperty(required=False)
	added_at = db.DateTimeProperty(auto_now_add = True)
	tot_votes = db.IntegerProperty(default=0)
	tot_upvotes = db.IntegerProperty(default=0)
	tot_downvotes = db.IntegerProperty(default=0)
	alternative_headlines = db.ListProperty(int)

class AltHeadline(db.Model):
	orig_headline_id = db.IntegerProperty(required=True)
	submitted_by = db.IntegerProperty(required=True)
	alt_headline = db.TextProperty(required=True)
	comments = db.StringProperty(required=False)
	added_at = db.DateTimeProperty(auto_now_add = True)
	tot_votes = db.IntegerProperty(default=0)

# Page Handlers

class Home(basic.Handler):
	#This handles the home page, showing the last 5 submitted headlines and whether or not the user has upvoted or downvoted those
	def get(self):
		offset = self.request.get('offset')
		if offset is not None and offset != '':
			offset = int(offset)
		else:
			offset = 0
		top_5_headlines = db.GqlQuery("SELECT * FROM Headline ORDER BY added_at DESC LIMIT 5 OFFSET %s"%offset)
		tot_headlines = db.Query(Headline).count()
		headlines_to_show = []
		count = 0
		for headline in top_5_headlines:
			upvoted = False
			downvoted = False
			if self.user:
				if headline.key().id() in self.user.upvoted_headlines:
					upvoted = True
				if headline.key().id() in self.user.downvoted_headlines:
					downvoted = True
			headlines_to_show.append({
				'headline': headline.headline,
				'id': headline.key().id(),
				'submitted_by': headline.submitted_by,
				'added_at': headline.added_at.strftime('%b-%d %I:%M %p'),
				'tot_votes': headline.tot_votes,
				'tot_upvotes': headline.tot_upvotes,
				'tot_downvotes': headline.tot_downvotes,
				'upvoted': upvoted,
				'downvoted': downvoted
				})
		if offset - 5 >= 0:
			show_prev = True
		else:
			show_prev = False
		
		if offset + 5 < tot_headlines:
			show_next = True
		else:
			show_next = False
		self.render('index.html', headlines_to_show = headlines_to_show, 
			offset = offset, show_prev = show_prev, show_next = show_next)

class Submit(basic.Handler):
	#this enables users to submit headlines
	def get(self):
		if self.user:
			self.render('submit.html')
		else:
			self.redirect('login.html?message_id=2')

	def post(self):
		if self.user:
			headline = self.request.get('headline')
			link_to_headline = self.request.get('link_to_headline')
			comments = self.request.get('comments')
			submitted_by = self.user.key().id()
			submission = Headline(headline=headline, link_to_headline = link_to_headline, 
				comments = comments, submitted_by = submitted_by)
			submission.put()
			self.user.submitted_headlines.append(submission.key().id())
			self.user.put()
			self.redirect('post.html?post_id=%d'%(submission.key().id()))
		else:
			self.render('signup.html', message = 'Please register before submitting a link', message_status = 'warning')

class Post(basic.Handler):
	#This enables users to see alternative headlines, and to submit new ones of their own
	def get(self):
		post_id = self.request.get('post_id')
		if post_id is not None and post_id != '':
			post_id = int(post_id)
			headline = Headline.get_by_id(post_id)
			headline_title = headline.headline
			submitted_by = int(headline.submitted_by)
			submitted_by = basic.User.by_id(submitted_by).username
			link = headline.link_to_headline
			comments = headline.comments
			if comments is None or comments == '':
				comments = None
			added_at = headline.added_at.strftime('%b-%d %I:%M %p')
			tot_votes = headline.tot_votes
			tot_upvotes = headline.tot_upvotes
			tot_downvotes = headline.tot_downvotes
			alternative_headlines = headline.alternative_headlines
			alternatives = []
			for h in alternative_headlines:
				upvoted = False
				if self.user:
					if h in self.user.upvoted_alt_headlines:
						upvoted = True
				alt = AltHeadline.get_by_id(h)
				alternatives.append({
					'submitted_by': basic.User.by_id(alt.submitted_by).username,
					'alt_headline': alt.alt_headline,
					'comments': alt.comments,
					'added_at': alt.added_at.strftime('%b-%d %I:%M %p'),
					'tot_votes': alt.tot_votes,
					'upvoted': upvoted,
					'id': h
					})

			upvoted = False
			downvoted = False
			if self.user:
				if post_id in self.user.upvoted_headlines:
					upvoted = True
				if post_id in self.user.downvoted_headlines:
					downvoted = True

			self.render('post.html', headline_title = headline_title, submitted_by = submitted_by, link = link,
				comments = comments, added_at = added_at, tot_votes = tot_votes, tot_upvotes = tot_upvotes,
				tot_downvotes = tot_downvotes, alternative_headlines = alternatives,
				upvoted = upvoted, downvoted = downvoted, post_id = post_id)
		else:
			self.response.out.write('an error occured')
	
	def post(self):
		if self.user:
			submitted_by = self.user.key().id()
			alt_headline = self.request.get('alternative_headline')
			comments = self.request.get('alternative_headline_comment')
			orig_headline_id = int(self.request.get('orig_headline_id'))
			alternative_headine = AltHeadline(orig_headline_id = orig_headline_id, submitted_by = submitted_by,
				alt_headline = alt_headline, comments = comments)
			alternative_headine.put()
			h = Headline.get_by_id(orig_headline_id)
			h.alternative_headlines.append(alternative_headine.key().id())
			h.put()
			self.user.submitted_alternatives.append(alternative_headine.key().id())
			self.user.put()
			self.redirect('post?post_id=%d'%orig_headline_id)
		else:
			self.render('signup.html', message = 'Please register before submitting a link', message_status = 'warning')

class Vote(basic.Handler):
	def get(self):
		self.redirect('/')
	def post(self):
		if self.user:
			user_id = self.user.key().id()
			post_type = self.request.get('post_type')
			post_id = int(self.request.get('post_id'))
			action = self.request.get('action')
			if post_type == 'main-headline':
				h = Headline.get_by_id(post_id)
				if action == 'neutral-to-upvote':
					h.tot_votes += 1
					h.tot_upvotes += 1
					self.user.upvoted_headlines.append(post_id)
				elif action == 'neutral-to-downvote':
					h.tot_votes += 1
					h.tot_downvotes += 1
					self.user.downvoted_headlines.append(post_id)
				elif action == 'upvote-to-neutral':
					h.tot_votes -= 1
					h.tot_upvotes -= 1
					self.user.upvoted_headlines.remove(post_id)
				elif action == 'downvote-to-neutral':
					h.tot_upvotes -=1
					h.tot_downvotes -= 1
					self.user.downvoted_headlines.remove(post_id)
				elif action == 'upvote-to-downvote':
					h.tot_upvotes -= 1
					h.tot_downvotes += 1
					self.user.upvoted_headlines.remove(post_id)
					self.user.downvoted_headlines.append(post_id)
				elif action == 'downvote-to-upvote':
					h.tot_upvotes += 1
					h.tot_downvotes -= 1
					self.user.upvoted_headlines.append(post_id)
					self.user.downvoted_headlines.remove(post_id)
				self.user.put()
				h.put()
			elif post_type == 'alt-headline':
				h = AltHeadline.get_by_id(post_id)
				if action == 'neutral-to-upvote':
					h.tot_votes += 1
					self.user.upvoted_alt_headlines.append(post_id)
				elif action == 'upvote-to-neutral':
					h.tot_votes -= 1
					self.user.upvoted_alt_headlines.remove(post_id)
				self.user.put()
				h.put()
			self.response.out.write('success')
		else:
			self.response.out.write('you must log in')

app = webapp2.WSGIApplication([('/', Home),
							   ('/login/?(?:.html)?', basic.Login),
							   ('/logout/?(?:.html)?', basic.Logout),
							   ('/signup/?(?:.html)?', basic.SignUp),
							   ('/index/?(?:.html)?', Home),
							   ('/submit/?(?:.html)?', Submit),
							   ('/post/?(?:.html)?', Post),
							   ('/vote/?(?:.html)?', Vote),],
							   debug=True)
