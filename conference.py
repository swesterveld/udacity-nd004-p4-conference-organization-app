#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

from datetime import datetime
from datetime import timedelta

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import StringMessage
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForms
from models import Session
from models import SessionForm
from models import SessionForms
from models import SessionType
from models import Wishlist
from models import WishlistForm
from models import Speaker
from models import SpeakerForm
from models import SpeakerForms
from models import TeeShirtSize

from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE

from utils import getUserId

import logging


# Helper method during development, to log values of variables
def log_values(d={}):
    logging.debug('\n'.join(["{}: {}".format(i[0], i[1]) for i in d.items()]))


EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": ["Default", "Topic"],
}

SESSION_DEFAULTS = {
    "duration": 30,
    "speakers": [],
    "typeOfSession": "NOT_SPECIFIED"
}

OPERATORS = {
    'EQ':   '=',
    'GT':   '>',
    'GTEQ': '>=',
    'LT':   '<',
    'LTEQ': '<=',
    'NE':   '!='
}

FIELDS = {
    'CITY': 'city',
    'TOPIC': 'topics',
    'MONTH': 'month',
    'MAX_ATTENDEES': 'maxAttendees',
}

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)

SESSION_GET_REQUEST_FILTERED = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1, required=True),
    typeOfSession=messages.StringField(2),  # XXX rename to filter? (generic)
)

SESSION_GET_REQUEST_SPEAKER = endpoints.ResourceContainer(
    message_types.VoidMessage,
    speaker=messages.StringField(1),
)

SESSION_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1),
)

SPKR_POST_REQUEST = endpoints.ResourceContainer(
    SpeakerForm,
    websafeKey=messages.StringField(1),
    )

GENERIC_WEBSAFEKEY_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeKey=messages.StringField(1, required=True),
)

SESSION_POST_REQUEST_MODIFY_SPEAKERS = endpoints.ResourceContainer(
    websafeSessionKey=messages.StringField(1, required=True),
    websafeSpeakerKey=messages.StringField(2, required=True),
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference', version='v1', audiences=[ANDROID_AUDIENCE],
               allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID,
                                   ANDROID_CLIENT_ID, IOS_CLIENT_ID],
               scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """ Conference API v0.1
    """

    @staticmethod
    def get_authed_user():
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization Required')
        return user

# - - - Conference objects - - - - - - - - - - - - - - - - -

    def _copyConferenceToForm(self, conf, displayName):
        """ Copy relevant fields from Conference to ConferenceForm.
        """
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf

    def _createConferenceObject(self, request):
        """ Create or update Conference object

        This method will return a ConferenceForm/request.
        """
        # preload necessary data items
        user = self.get_authed_user()
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException(
                "Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing
        # (both data model & outbound Message)
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]
                setattr(request, df, DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on
        # start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10],
                                                  "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10],
                                                "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees, if it's not
        # filled in on creation
        if (data["seatsAvailable"] is None) and (data["maxAttendees"] > 0):
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        prof_key = ndb.Key(Profile, user_id)
        conf_id = Conference.allocate_ids(size=1, parent=prof_key)[0]
        conf_key = ndb.Key(Conference, conf_id, parent=prof_key)
        data['key'] = conf_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
                              'conferenceInfo': repr(request)},
                      url='/tasks/send_confirmation_email')
        return request

    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = self.get_authed_user()
        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: {}'.format(
                    request.websafeConferenceKey)
                )

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))

    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
                      http_method='POST', name='createConference')
    def createConference(self, request):
        """ Create new conference.
        """
        return self._createConferenceObject(request)

    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
                      path='conference/{websafeConferenceKey}',
                      http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """ Update conference with provided fields

        This method will return a ConferenceForm with updated info.
        """
        return self._updateConferenceObject(request)

    @endpoints.method(GENERIC_WEBSAFEKEY_REQUEST, ConferenceForm,
                      path='conference/{websafeKey}',
                      http_method='GET', name='getConference')
    def getConference(self, request):
        """ Return requested conference (by websafeKey)
        """
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: {}'.format(
                    request.websafeKey)
                )
        prof = conf.key.parent().get()
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
                      path='conferences/created',
                      http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """ Return conferences created by user
        """
        # make sure user is authed
        user = self.get_authed_user()
        user_id = getUserId(user)

        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[
                self._copyConferenceToForm(conf, getattr(prof, 'displayName'))
                for conf in confs]
        )

    def _getQuery(self, request):
        """ Return formatted query from the submitted filters
        """
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(
                filtr["field"],
                filtr["operator"],
                filtr["value"])
            q = q.filter(formatted_query)
        return q

    def _formatFilters(self, filters):
        """ Parse, check validity and format user supplied filters
        """
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name)
                     for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException(
                    "Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous
                # filters disallow the filter if inequality was performed on a
                # different field before track the field on which the
                # inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException(
                        "Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)

    def _getConferenceOrganisers(self, conferences):
        """ Return a dict with organiser id's and names

        The dictionary has organiser id's as keys, and their names as values,
        based on queried conferences.
        """
        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId))
                      for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName
        return names

    @endpoints.method(ConferenceQueryForms, ConferenceForms,
                      path='conferences/query',
                      http_method='POST',
                      name='queryConferences')
    def queryConferences(self, request):
        """ Query for conferences.
        """
        conferences = self._getQuery(request)

        names = self._getConferenceOrganisers(conferences)
        # return individual ConferenceForm object per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(
                conf, names[conf.organizerUserId]) for conf in conferences]
        )

    # TASK 3
    def _intersectQueries(self, q1, q2):
        """ Return objects according to an intersection of two queries
        """
        return ndb.get_multi(
            set(q1.fetch(keys_only=True))
            & set(q2.fetch(keys_only=True)))

    # TASK 3
    @endpoints.method(message_types.VoidMessage, ConferenceForms,
                      path='conferences/upcoming',
                      http_method='POST',
                      name='getUpcomingConferences')
    def getUpcomingConferences(self, request):
        """ List all conferences that will be held in the upcoming three months
        """
        date_today = datetime.today().date()
        date_until = (date_today + timedelta(3*365/12))

        confs_from = Conference.query(
            Conference.endDate >= date_today)
        confs_till = Conference.query(
            Conference.startDate <= date_until
        )

        confs = self._intersectQueries(confs_from, confs_till)
        names = self._getConferenceOrganisers(confs)

        return ConferenceForms(
            items=[self._copyConferenceToForm(
                conf, names[conf.organizerUserId]) for conf in confs])

    # TASK 3
    @endpoints.method(message_types.VoidMessage, SessionForms,
                      path='sessions/nonworkshopbefore7',
                      http_method='GET', name='getNonWorkshopsBeforeSevenPM')
    def getNonWorkshopsBeforeSevenPM(self, request):
        """ Only show non-workshop sessions before 7PM
        """
        non_workshop = Session.query(
            Session.typeOfSession != 'WORKSHOP')
        before_seven = Session.query(
            # XXX replace startTime with endTime (which has to be
            # calculated first
            Session.startTime < datetime.strptime("19:00", "%H:%M").time())

        sessions = self._intersectQueries(non_workshop, before_seven)

        return SessionForms(
            items=[self._copySessionToForm(sess) for sess in sessions])

    # TASK 3
    @endpoints.method(message_types.VoidMessage, ConferenceForms,
                      path='conferences/not_sold_out_in_amsterdam',
                      http_method='GET',
                      name='getConferencesNotSoldOutInAmsterdam')
    def getConferencesNotSoldOutInAmsterdam(self, request):
        """ Only show conferences in Amsterdam that are not sold out
        """
        in_amsterdam = Conference.query(
            Conference.city == 'Amsterdam')
        not_sold_out = Conference.query(
            Conference.seatsAvailable > 0)

        confs = self._intersectQueries(in_amsterdam, not_sold_out)
        names = self._getConferenceOrganisers(confs)

        return ConferenceForms(
            items=[self._copyConferenceToForm(
                conf, names[conf.organizerUserId]) for conf in confs])

# - - - Session objects - - - - - - - - - - - - - - - - - - -

    def _copySessionToForm(self, session):
        """ Copy relevant fields from Session to SessionForm
        """
        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(session, field.name):
                # XXX Save an endTime when startTime and duration is
                # both given
                if field.name in ('date', 'startTime'):
                    # convert Date and Time to date and time string
                    setattr(sf, field.name, str(getattr(session, field.name)))
                elif field.name == 'typeOfSession':
                    # convert typeOfSession string to Enum
                    setattr(sf, field.name, getattr(SessionType,
                            getattr(session, field.name)))
                elif field.name == 'speakers':
                    setattr(sf, field.name, [str(speaker)
                            for speaker in getattr(session, field.name)])
                else:
                    # just copy the others
                    setattr(sf, field.name, getattr(session, field.name))
            elif field.name == "websafeKey":
                setattr(sf, field.name, session.key.urlsafe())
        sf.check_initialized()
        return sf

    def _createSessionObject(self, request):
        """ Create or update Session object, returning SessionForm/request
        """
        # preload necesarry data items
        user = self.get_authed_user()
        user_id = getUserId(user)

        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key {}'.format(
                    request.websafeConferenceKey)
            )

        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner of the conference may create a session.'
            )

        if not request.name:
            raise endpoints.BadRequestException(
                "Session 'name' field required")
        if not request.websafeConferenceKey:
            raise endpoints.BadRequestException(
                "Session 'websafeConferenceKey' field required")

        # copy SessionForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        del data['websafeKey']
        del data['websafeConferenceKey']

        # add default values for those missing (both data model &
        # outbound Message)
        for sf in SESSION_DEFAULTS:
            if data[sf] in (None, []):
                data[sf] = SESSION_DEFAULTS[sf]
                setattr(request, sf, SESSION_DEFAULTS[sf])

        # convert date from string to Date object
        if data['date']:
            data['date'] = datetime.strptime(data['date'], "%Y-%m-%d").date()

        # convert startTime from string to Time
        if data['startTime']:
            data['startTime'] = datetime.strptime(data['startTime'][:5],
                                                  "%H:%M").time()

        data['typeOfSession'] = str(data['typeOfSession'])
        if data['speakers']:
            data['speakers'] = [ndb.Key(
                Speaker, speaker) for speaker in data['speakers']]

        # generate Conference Key based on websafeConferenceKey and
        # Session ID based on Conference Key and get Session websafe key
        # from ID.
        conf_key = ndb.Key(Conference, request.websafeConferenceKey)
        sess_id = Session.allocate_ids(size=1, parent=conf_key)[0]
        sess_key = ndb.Key(Session, sess_id, parent=conf_key)
        data['key'] = sess_key

        # create Session, send email to organizer confirming creation of
        # Session and return (modified) SessionForm
        session = Session(**data).put()
        taskqueue.add(params={'email': user.email(),
                      'sessionInfo': repr(request)},
                      url='/tasks/send_confirmation_email')
        return self._copySessionToForm(session.get())

    def _updateSpeakersForSession(self, request, add):
        """ Based on the calling endpoint, add or remove a Speaker
        """
        session = ndb.Key(urlsafe=request.websafeSessionKey).get()
        if not session:
            raise endpoints.NotFoundException(
                'No session found with key: {}'.format(
                    request.websafeSessionKey
                )
            )

        spkr_key = ndb.Key(urlsafe=request.websafeSpeakerKey)
        if not spkr_key:
            raise endpoints.NotFoundException(
                'No speaker found with key: {}'.format(
                    request.websafeSpeakerKey
                )
            )

        if add:
            if spkr_key not in session.speakers:
                session.speakers.append(spkr_key)
                session.put()
        else:
            if spkr_key in session.speakers:
                session.speakers.remove(spkr_key)
                session.put()

        return self._copySessionToForm(session)

    @endpoints.method(SESSION_POST_REQUEST_MODIFY_SPEAKERS, SessionForm,
                      http_method='PUT', name='addSpeakerToSession')
    def addSpeakerToSession(self, request):
        """ Add a Speaker to a Session
        """
        return self._updateSpeakersForSession(request, add=True)

    @endpoints.method(SESSION_POST_REQUEST_MODIFY_SPEAKERS, SessionForm,
                      http_method='PUT', name='removeSpeakerFromSession')
    def removeSpeakerFromSession(self, request):
        """ Remove a Speaker from a Session
        """
        return self._updateSpeakersForSession(request, add=False)

    def _getSessions(self, request, typeFilter=None):
        conf_key = ndb.Key(Conference, request.websafeKey)

        if not conf_key:
            raise endpoints.NotFoundException(
                'No conference found with key {}'.format(
                    request.websafeKey
                )
            )

        sessions = Session.query(ancestor=conf_key)

        # Apply filters, if any.
        if typeFilter:
            sessions = sessions.filter(Session.typeOfSession == typeFilter)

        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )

    @endpoints.method(GENERIC_WEBSAFEKEY_REQUEST, SessionForms,
                      path='conference/{websafeKey}/sessions',
                      http_method='GET', name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """ Given a conference with a websafeKey, return all sessions
        """
        return self._getSessions(request)

    @endpoints.method(SESSION_GET_REQUEST_FILTERED, SessionForms,
                      path='sessions/type/{typeOfSession}',
                      http_method='GET', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """ Get all sessions of a specified type (eg lecture, keynote, etc.)

        The sessions aer limited to a conference with a given
        websafeConferenceKey
        """
        # XXX Maybe prepare a filter to use for a generic version of
        # _getSessions?
        return self._getSessions(request, typeFilter=request.typeOfSession)

    @endpoints.method(SESSION_GET_REQUEST_SPEAKER, SessionForms,
                      path='sessions/speaker/{speaker}',
                      http_method='GET', name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """ Get all sessions by a particular speaker given

        This returns sessions accross all conferences.
        """
        spkr_key = ndb.Key(urlsafe=request.speaker)
        sessions = Session.query(Session.speakers == spkr_key)

        return SessionForms(
            items=[self._copySessionToForm(session)
                   for session in sessions])

    @endpoints.method(SESSION_POST_REQUEST, SessionForm,
                      path='conference/{websafeConferenceKey}/session',
                      http_method='POST', name='createSession')
    def createSession(self, request):
        """ Create a new session for a given conference
        """
        return self._createSessionObject(request)


# - - - Speaker objects - - - - - - - - - - - - - - - - - - -

    def _copySpeakerToForm(self, speaker):
        """ Copy relevant fields from Speaker to SpeakerForm
        """
        sf = SpeakerForm()
        for field in sf.all_fields():
            if hasattr(speaker, field.name):
                setattr(sf, field.name, getattr(speaker, field.name))
            elif field.name == "websafeKey":
                setattr(sf, field.name, speaker.key.urlsafe())
        sf.check_initialized()
        return sf

    def _createSpeakerObject(self, request):
        """ Create or update Speaker object, returning SpeakerForm
        """

        if not request.name:
            raise endpoints.BadRequestException(
                "Session 'name' field required")

        # copy SpeakerForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        del data['websafeKey']

        s_id = Speaker.allocate_ids(size=1)[0]
        s_key = ndb.Key(Speaker, s_id)
        data['key'] = s_key

        spkr_key = Speaker(**data).put()
        return self._copySpeakerToForm(spkr_key.get())

    def _getSpeakers(self, request, nameFilter=None):
        """ Return speakers, with the option to filter on name
        """
        speakers = Speaker.query()

        if nameFilter:
            speakers.filter(Speaker.name == nameFilter)

        return SpeakerForms(
            items=[self._copySpeakerToForm(speaker) for speaker in speakers]
        )

    @endpoints.method(message_types.VoidMessage, SpeakerForms,
                      path='speakers', http_method='GET',
                      name='getSpeakers')
    def getSpeakers(self, request):
        """ Return all speakers
        """
        return self._getSpeakers(request)

    @endpoints.method(SPKR_POST_REQUEST, SpeakerForm,
                      path='speaker',
                      http_method='POST', name='createSpeaker')
    def createSpeaker(self, request):
        """ Create a new speaker
        """
        return self._createSpeakerObject(request)

# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    def _copyProfileToForm(self, prof):
        """ Copy relevant fields from Profile to ProfileForm
        """
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(TeeShirtSize,
                            getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf

    def _getProfileFromUser(self):
        """ Return user Profile from datastore

        This method will create a new profile if non-existent.
        """
        # make sure user is authed
        user = self.get_authed_user()

        # get Profile from datastore
        user_id = getUserId(user)
        prof_key = ndb.Key(Profile, user_id)
        profile = prof_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key=prof_key,
                displayName=user.nickname(),
                mainEmail=user.email(),
                teeShirtSize=str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile      # return Profile

    def _doProfile(self, save_request=None):
        """ Get user Profile and return to user, possibly updating it first
        """
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        # if field == 'teeShirtSize':
                        #     setattr(prof, field, str(val).upper())
                        # else:
                        #     setattr(prof, field, val)
                        prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)

    @endpoints.method(message_types.VoidMessage, ProfileForm,
                      path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """ Return user profile
        """
        return self._doProfile()

    @endpoints.method(ProfileMiniForm, ProfileForm,
                      path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """ Update & return user profile
        """
        return self._doProfile(request)


# - - - Wishlists - - - - - - - - - - - - - - - - - - - - - -

    def _copyWishlistToForm(self, wishlist):
        """ Copy relevant fields from Wishlist to WishlistForm
        """
        wf = WishlistForm()
        for field in wf.all_fields():
            if hasattr(wishlist, field.name):
                if field.name == 'session':
                    setattr(wf, field.name, str(getattr(wishlist, field.name)))
                else:
                    setattr(wf, field.name, getattr(wishlist, field.name))
            elif field.name == "websafeKey":
                setattr(wf, field.name, wishlist.key.urlsafe())
        wf.check_initialized()
        return wf

    def _createWishlistObject(self, request):
        """ Create or update Wishlist object, returning WishlistForm
        """
        # Preload and validate necessary data items
        user = self.get_authed_user()
        user_id = getUserId(user)
        prof_key = ndb.Key(Profile, user_id)

        if not request.websafeKey:
            raise endpoints.BadRequestException('Session websafeKey required')

        session = ndb.Key(urlsafe=request.websafeKey)
        if not session:
            raise endpoints.NotFoundException(
                'No session found with key: {}'.format(request.websafeKey)
            )

        # copy WishlistForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name)
                for field in request.all_fields()}
        del data['websafeKey']

        sess_key = ndb.Key(urlsafe=request.websafeKey)
        data['session'] = sess_key

        wishlist_id = Wishlist.allocate_ids(size=1, parent=prof_key)[0]
        wishlist_key = ndb.Key(Wishlist, wishlist_id, parent=prof_key)
        data['key'] = wishlist_key

        Wishlist(**data).put()

        return self._copyWishlistToForm(wishlist_key.get())

    @endpoints.method(GENERIC_WEBSAFEKEY_REQUEST, WishlistForm,
                      path='profile/wishlist', http_method='POST',
                      name='createWishlist')
    def createWishlist(self, request):
        """ Create a new Wishlist
        """
        return self._createWishlistObject(request)

    def _getSessionsInWishlist(self):
        """ Helper method to get Sessions from the wishlist
        """
        user = self.get_authed_user()
        user_id = getUserId(user)
        prof_key = ndb.Key(Profile, user_id)

        wish_keys = Wishlist.query(ancestor=prof_key)
        sess_keys = [wish_key.session for wish_key in wish_keys]

        if sess_keys in (None, []):
            raise endpoints.BadRequestException(
                'No wishlist found: {}'.format(sess_keys))
        return ndb.get_multi(sess_keys)

    @endpoints.method(message_types.VoidMessage, SessionForms,
                      path='profile/wishlist', http_method='GET',
                      name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        """ Get sessions that the user is interested in
        """
        sessions = self._getSessionsInWishlist()

        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )

    def _updateSessionsInWishlist(self, request, add=True):
        """ Add or remove a Session from the Wishlist

        Whether a session will be added or removed is based on the calling
        endpoint
        """
        # Preload and validate necessary data items
        user = self.get_authed_user()

        session = ndb.Key(urlsafe=request.websafeKey)
        if not session:
            raise endpoints.BadRequestException(
                'No session found for key: {}'.format(request.websafeKey)
            )

        user_id = getUserId(user)
        prof_key = ndb.Key(Profile, user_id)
        wishlist = Wishlist.query(ancestor=prof_key)

        if add:
            # Check whether the given websafeKey is already in the wishlist
            if wishlist.filter(Wishlist.session == session).count() > 0:
                raise endpoints.BadRequestException(
                    'Session has already been added to your wishlist')

            self._createWishlistObject(request)

            return self._copySessionToForm(session.get())
        else:
            sessions = wishlist.filter(Wishlist.session == session).fetch()
            if len(sessions) != 0:
                sessions[0].key.delete()

            updated_wishlist = self._getSessionsInWishlist()

            return SessionForms(
                items=[self._copySessionToForm(item)
                       for item in updated_wishlist]
            )

    @endpoints.method(GENERIC_WEBSAFEKEY_REQUEST, SessionForm,
                      path='profile/wishlist/add', http_method='POST',
                      name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """ Add a given session to the user's wishlist

        The wishlist is made to keep track of sessions a user is interested in
        attending.
        """
        return self._updateSessionsInWishlist(request, add=True)

    @endpoints.method(GENERIC_WEBSAFEKEY_REQUEST, SessionForms,
                      path='profile/wishlist/delete', http_method='DELETE',
                      name='deleteSessionInWishList')
    def deleteSessionInWishlist(self, request):
        """ Remove a given session from the user's wishlist

        In case a user isn't interested in visiting the session anymore.
        """
        return self._updateSessionsInWishlist(request, add=False)

# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """ Create Announcement & assign to memcache

        This is used by the memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement

    @endpoints.method(message_types.VoidMessage, StringMessage,
                      path='conference/announcement/get',
                      http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """ Return Announcement from memcache
        """
        return StringMessage(
            data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or "")


# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """ Register or unregister user for selected conference
        """
        retval = None
        prof = self._getProfileFromUser()  # get user Profile

        # check if conf exists given websafeConferenceKey
        # get conference; check that it exists
        wsck = request.websafeKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
                      path='conferences/attending',
                      http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """ Get list of conferences that user has registered for
        """
        prof = self._getProfileFromUser()  # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck)
                     for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId)
                      for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[
            self._copyConferenceToForm(conf, names[conf.organizerUserId])
            for conf in conferences]
        )

    @endpoints.method(GENERIC_WEBSAFEKEY_REQUEST, BooleanMessage,
                      path='conference/{websafeKey}/register',
                      http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """ Register user for selected conference
        """
        return self._conferenceRegistration(request)

    @endpoints.method(GENERIC_WEBSAFEKEY_REQUEST, BooleanMessage,
                      path='conference/{websafeKey}/unregister',
                      http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """ Unregister user for selected conference
        """
        return self._conferenceRegistration(request, reg=False)

api = endpoints.api_server([ConferenceApi])  # register API
