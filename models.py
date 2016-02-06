#!/usr/bin/env python

"""models.py

Udacity conference server-side Python App Engine data & ProtoRPC models

$Id: models.py,v 1.1 2014/05/24 22:01:10 wesc Exp $

created/forked from conferences.py by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb


class ConflictException(endpoints.ServiceException):
    """Exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT


class Profile(ndb.Model):
    """User profile object"""
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    teeShirtSize = ndb.StringProperty(default='NOT_SPECIFIED')
    conferenceKeysToAttend = ndb.StringProperty(repeated=True)


class ProfileMiniForm(messages.Message):
    """Form message for update on Profile"""
    displayName = messages.StringField(1)
    teeShirtSize = messages.EnumField('TeeShirtSize', 2)


class ProfileForm(messages.Message):
    """Outbound form message for Profile"""
    displayName = messages.StringField(1)
    mainEmail = messages.StringField(2)
    teeShirtSize = messages.EnumField('TeeShirtSize', 3)
    conferenceKeysToAttend = messages.StringField(4, repeated=True)


class StringMessage(messages.Message):
    """Outbound message for (single) string"""
    data = messages.StringField(1, required=True)


class BooleanMessage(messages.Message):
    """Outbound message for Boolean value"""
    data = messages.BooleanField(1)


class Conference(ndb.Model):
    """Conference object"""
    name            = ndb.StringProperty(required=True)
    description     = ndb.StringProperty()
    organizerUserId = ndb.StringProperty()
    topics          = ndb.StringProperty(repeated=True)
    city            = ndb.StringProperty()
    startDate       = ndb.DateProperty()
    month           = ndb.IntegerProperty()
    endDate         = ndb.DateProperty()
    maxAttendees    = ndb.IntegerProperty()
    seatsAvailable  = ndb.IntegerProperty()


class ConferenceForm(messages.Message):
    """Outbound form message for Conference"""
    name            = messages.StringField(1)
    description     = messages.StringField(2)
    organizerUserId = messages.StringField(3)
    topics          = messages.StringField(4, repeated=True)
    city            = messages.StringField(5)
    startDate       = messages.StringField(6)  #DateTimeField()
    month           = messages.IntegerField(7, variant=messages.Variant.INT32)
    maxAttendees    = messages.IntegerField(8, variant=messages.Variant.INT32)
    seatsAvailable  = messages.IntegerField(9, variant=messages.Variant.INT32)
    endDate         = messages.StringField(10)  #DateTimeField()
    websafeKey      = messages.StringField(11)
    organizerDisplayName = messages.StringField(12)


class ConferenceForms(messages.Message):
    """Outbound form message for multiple Conference messages"""
    items = messages.MessageField(ConferenceForm, 1, repeated=True)


class Session(ndb.Model):
    """Session object"""
    name            = ndb.StringProperty(required=True)
    highlights      = ndb.StringProperty()
    duration        = ndb.IntegerProperty()
    typeOfSession   = ndb.StringProperty(default='NOT_SPECIFIED')
    date            = ndb.DateProperty()
    startTime       = ndb.TimeProperty()
    speakers        = ndb.StringProperty(repeated=True)
    websafeConferenceKey = ndb.StringProperty(required=True)

class SessionForm(messages.Message):
    """Outbound form message for Session"""
    name            = messages.StringField(1)
    highlights      = messages.StringField(2)
    duration        = messages.IntegerField(3)
    typeOfSession   = messages.EnumField('SessionType', 4, default='NOT_SPECIFIED')
    date            = messages.StringField(5)
    startTime       = messages.StringField(6)
    speakers        = messages.StringField(7, repeated=True)
    websafeKey      = messages.StringField(8)


class SessionForms(messages.Message):
    """Outbound form message for multiple Session messages"""
    items = messages.MessageField(SessionForm, 1, repeated=True)


class Speaker(ndb.Model):
    """Speaker object"""
    name    = ndb.StringProperty(required=True)
    twitter = ndb.StringProperty()
    website = ndb.StringProperty()


class SpeakerForm(messages.Message):
    """Outbound form message for Speaker"""
    name        = messages.StringField(1)
    twitter     = messages.StringField(2)
    website     = messages.StringField(3)
    websafeKey  = messages.StringField(4)


class SpeakerForms(messages.Message):
    """Outbound form message for multiple Speaker messages"""
    items = messages.MessageField(SpeakerForm, 1, repeated=True)


class TeeShirtSize(messages.Enum):
    """T-shirt size enumeration value"""
    NOT_SPECIFIED = 1
    XS_M = 2
    XS_W = 3
    S_M = 4
    S_W = 5
    M_M = 6
    M_W = 7
    L_M = 8
    L_W = 9
    XL_M = 10
    XL_W = 11
    XXL_M = 12
    XXL_W = 13
    XXXL_M = 14
    XXXL_W = 15


class SessionType(messages.Enum):
    """Session type enumeration value"""
    NOT_SPECIFIED = 1
    WORKSHOP = 2
    LECTURE = 3
    KEYNOTE = 4
    BREAK = 5
    OPEN_SPACE = 6


class ConferenceQueryForm(messages.Message):
    """Inbound form message for Conference query"""
    field       = messages.StringField(1)
    operator    = messages.StringField(2)
    value       = messages.StringField(3)


class ConferenceQueryForms(messages.Message):
    """Inbound form message for multiple ConferenceQueryForm messages"""
    filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)
