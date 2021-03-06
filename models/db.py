# -*- coding: utf-8 -*-
# by default give a view/generic.extension to all actions from localhost
# none otherwise. a pattern can be 'controller/function.extension'
response.generic_patterns = ['*'] if request.is_local else []

#########################################################################
# Symposium Table
#########################################################################
db.define_table('symposium',
    Field('name','string',required=True, notnull=True, label=T("Symposium Name")),
    Field('sid', 'string', required=True, notnull=True, unique=True, label=T("Symposium UID"),
           comment=T("This is a short id for the symposium to be used in the url. Example: ugradresearch2011.")),
    Field('reg_start', 'datetime', required=True, notnull=True, label=T("Registration Start")),
    Field('reg_end', 'datetime', required=True, notnull=True, label=T("Registration End")),
    Field('event_date', 'date', required=True, notnull=True, label=T("Symposium Date")),
    Field('extra_info', 'text', label=T("Additional Information")),
    format='%(name)s: %(event_date)s'
)

#Add after created so we don't override the unique test
db.symposium.sid.requires.insert(0,IS_SLUG())

db.define_table('timeblock',
    Field('start_time', 'time', required=True, notnull=True),
    Field('desc', 'text'),
    Field('symposium', db.symposium, writable=False),
    format = "%(start_time)s: %(desc)s",
)

db.define_table('room',
    Field('symposium', db.symposium, writable=False),
    Field('name', required=True, notnull=True),
    Field('location'),
    format = "%(name)s: %(location)s"
)

db.define_table('session',
    Field('name', required=True, notnull=True),
    Field('theme'),
    Field('timeblock', db.timeblock, writable=False),
    Field('room', db.room, writable=False),
    Hidden('judges', 'list:reference auth_user', default=[]),
    format = "%(timeblock)s %(name)s"
)

db.define_table('format',
    Field('name', required=True, notnull=True),
    Field('duration', 'integer', required=True, notnull=True, default=15),
    Field('symposium',db.symposium, writable=False),
    format = "%(name)s"
)

db.define_table('category',
    Field('name'),
    Field('symposium', db.symposium, writable=False),
    format = "%(name)s"
)

db.define_table('reviewer',
    Field('reviewer', db.auth_user,
        widget=SQLFORM.widgets.autocomplete(request, db.auth_user.search_name,
                   limitby=(0,10), min_length=2, id_field=db.auth_user.id)),
    Field('symposium', db.symposium, writable=False),
    Field('global_reviewer', 'boolean', label=T("Global Reviewer"), comment=T("Check to make Global Reviewer")),
    Field('categories', 'list:reference category',widget=SQLFORM.widgets.checkboxes.widget,
        comment=T("Check all categories you wish to give to this reviewer (Not Needed for global reviewers).")),
    format = "%(reviewer)s (%(symposium)s"
)

#########################################################################
# Paper Table
#########################################################################
db.define_table('paper',
    Field('title', 'string', required=True, notnull=True,
            label=T("Paper Title"), comment="*"),
            
    Field('description', 'text', required=True, notnull=True,
            label=T("Paper Description"), comment=XML(T("""*
                <b>This is the body text of your abstract.</b><br/>
                It will be used as the main body of an automatically generated
                abstract for your submission, authors and mentors can be managed later on.
                """))),
            
    Field('paper', 'upload', label=T("Paper Upload"), autodelete=True,
          comment=XML(T("""
              You may upload a copy of your paper now or come back later.
              <b>You must upload your paper before you submit for approval.</b>
              At anytime (even after approval) You may to add additional presentation
              materials from the manage my papers screen.
              """))),
                     
    Field('status', 'string', requires=IS_IN_SET(PAPER_STATUS), default=PAPER_STATUS[0],
          label=T("Paper Status"), writable=False),
          
    Field('category', db.category,
        comment=T("Pick the category that best matches your paper.  This will be used for scheduling purposes.")),
    
    Field('format', db.format, label=T("Presentation Format"),
       comment=T("The method/format of the presentation you will give at the symposium.")),
    
    Field('symposium', 'reference symposium', writable=False),
    
    Hidden('created', 'datetime', default=request.now),
    Hidden('created_by', db.auth_user, default=auth.user_id),
    
    Hidden('modified', 'datetime', default=request.now, update=request.now),
    Hidden('modified_by', db.auth_user, default=auth.user_id, update=auth.user_id),

    Hidden('session', db.session, ondelete="NO ACTION"),
    Hidden('session_pos', 'integer'),
    
    format='%(title)s'
)

def paper_update(form):
    """
    Resets the paper status to 0, need to be submitted for approval
    """
    form.vars.status=PAPER_STATUS[0]
crud.settings.update_onvalidation.paper.append(paper_update)


db.define_table('paper_associations',
    Hidden('paper', db.paper),
    Field('person', db.auth_user, writable=False, label=T("Person/Official Affiliation")),
    Hidden('type', requires=IS_IN_SET(PAPER_ASSOCIATIONS)),
    Field('person_association', label=T("Paper Specific Affiliation")),
    Hidden('created', 'datetime', default=request.now),
    Hidden('created_by', db.auth_user, default=auth.user_id),
    Hidden('modified', 'datetime', default=request.now, update=request.now),
    Hidden('modified_by', db.auth_user, default=auth.user_id, update=auth.user_id)
)

#########################################################################
# Paper_comment Table, used to keep track of the review process
#########################################################################
db.define_table('paper_comment',
    Hidden('paper', db.paper, writable=False),
    Hidden('author', db.auth_user, default=auth.user.id if auth.user else None),
    Field('status', 'string', requires=IS_IN_SET(PAPER_STATUS)),
    Hidden('created', 'datetime', default=request.now),
    Field('comment', 'text')
    )

def paper_comment(form):
    """
    When a comment has been posted, this method is called to update
    the paper's status and email all authors that there has been an
    update on their paper's status.
    """
    # Update Paper Status
    comment = db.paper_comment(form.vars.id)
    paper = db.paper(comment.paper)
    paper.update_record(status=comment.status)

    # Email All associated users
    people = db(db.paper_associations.paper==paper).select(db.paper_associations.person)
        
    author_list = [db.auth_user(person.person).email for person in people]

    mail.send(to=author_list, subject=T("Symposium Paper Status Update"),
    message=response.render('email_templates/paper_updated.txt', {
        "title":paper.title,
        "author":db.auth_user._format % db.auth_user(comment.author),
        "status":comment.status,
        "comment":comment.comment,
        "url":"http://%s%s" % (request.env.http_host, URL("papers","edit"))
        }))

crud.settings.create_onaccept.paper_comment.append(paper_comment)

#########################################################################
# Paper_attachment Table, used to attach additional files like
# presentation materials
#########################################################################
db.define_table('paper_attachment',
    Field('paper', db.paper, writable=False),
    Field('author', db.auth_user, default=auth.user.id if auth.user else None, writable=False),
    Field('title', 'string', required=True, notnull=True, label=T("Title")),
    Field('file', 'upload', required=True, notnull=True),
    Field('created', 'datetime', default=request.now, writable=False),
    Field('comment', 'string', label=T("Short Comment/Description")),
    format = "%(title)s"
    )

db.define_table('page',
    Field('title', required=True),
    Field('url', required=True, requires=[IS_NOT_EMPTY(), IS_SLUG(check=True, error_message="only lowercase alphanumeric characters and non-repeated dashes")]),
    Field('body', 'text'),
    Hidden('symposium', db.symposium, requires=IS_EMPTY_OR(IS_IN_DB(db, db.symposium, db.symposium._format))),
    format = "%(title)s"
    )

#########################################################################
# Helper to create admin groups and accounts when the first user is
# created.  Also sets session pre-populate flag to cause the wiki-plugin
# to build its original pages
#########################################################################
def ensure_admin(form):
    """
    When a user is created for the first time, this function will
    create the admin and review groups and add the new user to thoes
    new groups.
    """
    if form.vars.id==1:
        auth.add_group(role = 'Symposium Admin')
        auth.add_membership('Symposium Admin', 1)
        
        # Request that plugin_wiki pre-populate pages
        session['pre-populate'] = True

auth.settings.register_onaccept=ensure_admin
