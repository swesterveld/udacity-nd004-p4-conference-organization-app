App Engine application for the Udacity training course.

## Products
- [App Engine][1]

## Language
- [Python][2]

## APIs
- [Google Cloud Endpoints][3]

## Setup Instructions
1. Update the value of `application` in `app.yaml` to the app ID you
   have registered in the App Engine admin console and would like to use to host
   your instance of this sample.
1. Update the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the
   [Developer Console][4].
1. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
1. (Optional) Mark the configuration files as unchanged as follows:
   `$ git update-index --assume-unchanged app.yaml settings.py static/js/app.js`
1. Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's running by visiting your local server's address (by default [localhost:8080][5].)
1. (Optional) Generate your client library(ies) with [the endpoints tool][6].
1. Deploy your application.

## Task 1: Add Sessions to a Conference
`Session` is implemented as a child of `Conference`, because that will make it
easier to quickly find all sessions of a conference. `Speaker` is implemented as
a separate model, because that will make it easier for re-use and to extend it
with properties. By using a repeatable `KeyProperty` for speakers of a `Session`,
it will be possible to treat it as a many-to-many relationship.

```python
class Session(ndb.Model):
    """Session object"""
    name            = ndb.StringProperty(required=True)
    highlights      = ndb.StringProperty()
    duration        = ndb.IntegerProperty()
    typeOfSession   = ndb.StringProperty(default='NOT_SPECIFIED')
    date            = ndb.DateProperty()
    startTime       = ndb.TimeProperty()
    speakers        = ndb.KeyProperty(kind='Speaker', repeated=True)

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
```

The following endpoint methods have been defined:

- `getConferenceSessions` -- This invokes a generic `_getSessions` method which
  returns a list of existing Sessions of a conference that matches the given
  webSafeConferenceKey.
- `getConferenceSessionsByType` -- This invokes a generic `_getSessions` method
  which returns a limited list of existing Sessions of a conference that matches
  the given webSafeConferenceKey. Because in this case the invokation of the
  generic `_getSessions` method is done with an extra parameter for filtering on
  type, it will limit the list Sessions according to the given type.
- `getSessionsBySpeaker` -- This method returns a list of Sessions accross all
  conferences, limited to the Sessions where the given speaker is in the list of
  speakers.
- `createSession` -- This invokes a `_createSessionObject` method which copies
  the data from the request to a new Session object.

The _updateSpeakersForSession method has been implemented as a generic method, to
invoke for both adding and removing Speakers of a Session. Like this, the
endpoints addSpeakerToSession and reomveSpeakerFromSession can be kept very clean.
Another generic method is _getSessions, with an optional parameter for filtering.
This makes it possible to have very light endpoints for specific filters, and have
the implementation of filtering at one place, according to the DRY principle.

[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://localhost:8080/
[6]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
