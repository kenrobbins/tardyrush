#!/bin/env python

import re, time
from datetime import datetime
import mechanize
from tardyrush import db, models

def post_to_vbulletin_3_7(url, forum_id, username, password, subject, message):
    retval = None

    url = url.strip('/')

    br = mechanize.Browser()
    br.open(url)

    def find_login_form(form):
        if re.search("login\.php", form.action):
            return True
        return False

    try:
        br.select_form(predicate=find_login_form)

        br["vb_login_username"] = username
        br["vb_login_password"] = password

        response = br.submit()

        if response:
            posturl = "%s/newthread.php?do=newthread&f=%d" % (url, forum_id)
            print "post url:", posturl
            br.open(posturl)

            br.select_form(name="vbform")

            if len(subject) > 85:
                subject = subject[:82] + '...'

            br["subject"] = subject
            br["message"] = message

            response = br.submit()

            print "response url:", response.geturl()

            m = re.search(r"#post([0-9]+)", response.geturl())
            if m and len(m.groups()):
                post_id = int(m.groups()[0])
                retval = "%s/showthread.php?p=%d" % (url, post_id)
    except Exception, e:
        print "vb 3.7 failed:", e, url, forum_id, username, password, subject

    return retval

###############################################################################

# get queued posts
# get bots
# for each post,
#       if bot.game_id is None or bot.game_id == post.game_id
#           post

team_bots = {}
def get_bots_for_team(team_id):
    if team_id in team_bots:
        return team_bots[team_id]

    bots = db.session.query(models.ForumBot).filter_by(team_id=team_id).all()
    team_bots[team_id] = bots
    return bots

posts = db.session.query(models.ForumBotQueuedPost).all()

commit = False
post_ids = []
for p in posts:
    remove = False
    bots = get_bots_for_team(p.team_id)

    for b in bots:
        if b.game_id is None or b.game_id == p.game_id:
            if b.type == models.ForumBot.TypeVBulletin3_7:
                print
                print "posting:", p.id, p.match_id, p.game_id, p.subject
                print "message:"
                print p.message
                print

                forum_post_url = post_to_vbulletin_3_7(\
                                    b.url, b.forum_id, b.user_name,
                                    b.password, p.subject, p.message)

                print "returned:", forum_post_url
                print

                if forum_post_url is not None:
                    p.match.forum_post_url = forum_post_url
                    commit = True
                    remove = True

    if p.date_created:
        time_since_created = datetime.utcnow() - p.date_created

        # remove if in the queue for more than 1 hour
        if time_since_created.seconds > (3600 * 1):
            remove = True
    else:
        remove = True

    if remove:
        post_ids.append(p.id)

if len(post_ids):
    commit = True
    db.session.query(models.ForumBotQueuedPost).\
            filter(models.ForumBotQueuedPost.id.in_(post_ids)).\
            delete(False)

if commit:
    db.session.commit()


