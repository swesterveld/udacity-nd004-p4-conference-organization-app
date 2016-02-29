# Project "Conference Organization App"

This code is the result I achieved for ***[Udacity Full Stack Web Developer Nanodegree](https://www.udacity.com/course/nd004) - Project 4: Conference Organization App***.
The app is built in [Python][1] to run on [Google App Engine][2]. [Google Cloud
Endpoints][3] have been used for the API.
Instructions on how to run the application can be found in the next section of
this README text.

This code has been *reviewed by me*. According to me, based on the rubric
used by the Udacity reviewer, this code at least:
- [x] Meets Specifications: App is architected as a Web Service API. (App
  Architecture)
- [x] Meets Specifications: App supports a variety of possible front-end
  clients. (App Architecture)
- [x] Exceeds Specifications: Student implements additional
  functionality such as an entity for speakers. (Task 1: Design Choices)
- [x] Exceeds Specifications: The README file includes an explanation of
  the design decissions behind the additional functionality. (Task 1: Design
  Choices)
- [x] Meets Specifications: Student response shows understanding of the
  process of data modeling and justifies their implementation decisions for
  the chosen data types. (Task 1: Design Choices)
- [x] Meets Specifications: Users are able to mark sessions they are
  interested in and retrieve their own current wishlist. (Task 2: Session
  Wishlist)
- [x] Meets Specifications: Users are able to delete a session from
  their wishlist. (Task 2: Session Wishlist)
- [x] Meets Specifications: The README file describes two additional
  query types that are consistent with the goals of the project. (Task 3:
  Additional Queries)
- [x] Meets Specifications: Both of the proposed queries are
  implemented. (Task 3: Additional Queries)
- [x] Meets Specifications: In the README, student describes the reason
  for the problem with the provided query. (Task 3: Additional Queries)
- [x] Exceeds Specifications: Student has implemented the proposed
  solution(s) in actual code. (Task 3: Additional Queries)
- [x] Meets Specifications: Student imlplements `getFeaturedSpeaker()`. (Task 4:
  Featured Speaker)
- [x] Meets Specifications: Students uses App Engine's Task Queue when
  implementing the featured speaker logic. (Task 4: Featured Speaker)
- [x] Meets Specifications: Code is ready for personal review and neatly
  formatted. (Code Quality)
- [x] Meets Specifications: Code follows an intuitive easy-to-follow
  logical structure. (Code Readability)
- [x] Meets Specifications: Comments are present and effectively explain
  longer code procedures. (Code Readability)
- [x] Meets Specifications: README file is included. (Documentation)
- [x] Meets Specifications: The README file provides details of all the
  steps required to successfully run the application. (Documentation)


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
1. Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's
   running by visiting your local server's address (by default [localhost:8080][5].)
1. (Optional) Generate your client library(ies) with [the endpoints tool][6].
1. Deploy your application.


## Testing
To test the API endpoints visit [the API explorer][7].


## Task 1: Add Sessions to a Conference
`Session` is implemented as a child of `Conference`, because that will make it
easier to quickly find all sessions of a conference. `Speaker` is implemented as
a separate model, because that will make it easier for re-use and to extend it
with properties. By using a repeatable `KeyProperty` for speakers of a session,
it will be possible to treat it as a many-to-many relationship.

```python
class Session(ndb.Model):
    """Session object
    """
    name            = ndb.StringProperty(required=True)
    highlights      = ndb.StringProperty()
    duration        = ndb.IntegerProperty()
    typeOfSession   = ndb.StringProperty(default='NOT_SPECIFIED')
    date            = ndb.DateProperty()
    startTime       = ndb.TimeProperty()
    speakers        = ndb.KeyProperty(kind='Speaker', repeated=True)

class SessionForm(messages.Message):
    """Outbound form message for Session
    """
    name            = messages.StringField(1)
    highlights      = messages.StringField(2)
    duration        = messages.IntegerField(3)
    typeOfSession   = messages.EnumField('SessionType', 4, default='NOT_SPECIFIED')
    date            = messages.StringField(5)
    startTime       = messages.StringField(6)
    speakers        = messages.StringField(7, repeated=True)
    websafeKey      = messages.StringField(8)


class SessionForms(messages.Message):
    """Outbound form message for multiple Session messages
    """
    items = messages.MessageField(SessionForm, 1, repeated=True)
```

The following endpoint methods have been defined:

- `getConferenceSessions` -- This invokes a generic `_getSessions` method which
  returns a list of existing sessions of a conference that matches the given
  `websafeKey`.
- `getConferenceSessionsByType` -- This invokes a generic `_getSessions` method
  which returns a limited list of existing sessions of a conference that matches
  the given webSafeConferenceKey. Because in this case the invocation of the
  generic `_getSessions` method is done with an extra parameter for filtering on
  type, which will be `None` by default, it will limit the list sessions
  according to the given type.
- `getSessionsBySpeaker` -- This method returns a list of sessions accross all
  conferences, limited to the sessions where the given speaker is in the list of
  speakers.
- `createSession` -- This invokes a `_createSessionObject` method that copies
  the data from the request to a new `Session` object.

The `_updateSpeakersForSession` method has been implemented as a generic method,
to invoke for both adding and removing speakers of a session. Like this, the
endpoints `addSpeakerToSession` and `removeSpeakerFromSession` can be kept very
clean. Another generic method is `_getSessions`, with an optional parameter for
filtering. This makes it possible to have very lightweight endpoints for
specific filters, and have the implementation of filtering at one place,
according to the DRY principle.

```python
    def _updateSpeakersForSession(self, request, add):
        """Based on the calling endpoint, add or remove a Speaker.
        """
        session = ndb.Key(urlsafe=request.websafeSessionKey).get()

        [...]

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
        """Add a Speaker to a Session.
        """
        return self._updateSpeakersForSession(request, add=True)

    @endpoints.method(SESSION_POST_REQUEST_MODIFY_SPEAKERS, SessionForm,
                      http_method='PUT', name='removeSpeakerFromSession')
    def removeSpeakerFromSession(self, request):
        """Remove a Speaker from a Session.
        """
        return self._updateSpeakersForSession(request, add=False)
```


## Task 2: Add Sessions to User Wishlist

The following endpoint methods have been defined:

- `addSessionToWishlist()` -- adds the session to the user's list of sessions
  they are interested in attending
- `getSessionsInWishlist()` -- query for all the sessions in a conference that
  the user is interested in
- `deleteSessionInWishlist()` -- removes the session from the user’s list of
  sessions they are interested in attending

The endpoint methods for adding and deleting are implemented on a similar way as
the previously mentioned methods for adding and deleting speakers. They invoke
a generic method called `_updateSessionsInWishlist` that will either add or
delete an item to or from the wishlist, based on a boolean-parameter.


## Task 3: Work on indexes and queries

### Come up with 2 additional queries

The following endpoint methods have been defined, with additional queries:

- `getUpcomingConferences` -- query for all conferences that will be
  held in the upcoming 3 months. This can be useful for users who want to check
  for conferences that will be held soon, but haven't attracted their attention
  yet. Or maybe for people who only know on 'short term' if they have time to
  visit a conference. The inner workings of this method are described in the
  next section.
- `getConferencesNotSoldOutInAmsterdam` -- this is a query I would be
  interested in myself, because I'm living in Amsterdam. Visiting a conference
  can take a lot of my precious time, especially when it's a conference abroad.
  And did you ever think about biking from home to the venue in 15 minutes,
  instead of flying for hours? And leaving from home means sleeping at home,
  which is a big plus as well :)

  This is basicly what the code does:
  ```python
      in_amsterdam = Conference.query(
          Conference.city == 'Amsterdam')
      not_sold_out = Conference.query(
          Conference.seatsAvailable > 0)

      confs = self._intersectQueries(in_amsterdam, not_sold_out)
      names = self._getConferenceOrganisers(confs)

      return ConferenceForms(
          items=[self._copyConferenceToForm(
              conf, names[conf.organizerUserId]) for conf in confs])
  ```
  (some of it is described in the next section)

### Query related problem with inequality filtering for multiple properties

According to the [docs][8], the Datastore API doesn't support inequality
filtering on multiple properties:

> Limitations: The Datastore enforces some restrictions on queries. Violating
> these will cause it to raise exceptions. For example, combining too many
> filters, using inequalities for multiple properties, or combining an
> inequality with a sort order on a different property are all currently
> disallowed. Also filters referencing multiple properties sometimes require
> secondary indexes to be configured.

When you try to filter queries on multiple properties, a `TypeError: Model is
not immutable` is raised. There are multiple approaches possible to tackle this
problem, of which I've chosen an implementation that intersects the results of
two queries. This is more or less what my first implementation with an
intersection looked like, to get all upcoming conferences for the next 3 months:

```python
    date_now = datetime.today().date()
    date_end = (date_now + timedelta(3*365/12))

    confs_from = Conference.query(
        Conference.endDate >= date_now)
    confs_till = Conference.query(
        Conference.startDate <= date_end
    )

    intersection = set(
        [c.key.urlsafe() for c in confs_from]) & set(
        [c.key.urlsafe() for c in confs_till])

    result = ndb.get_multi(
        [ndb.Key(urlsafe=item) for item in intersection]
    )
```

When I ran into a similar problem for filtering non-workshop sessions that are
not scheduled after 19:00, I decided to move the intersecting procedure to a
separate generic method:

```python
    def _intersectQueries(self, q1, q2):
        """ Return objects according to an intersection of two queries
        """
        return ndb.get_multi(set(
            q1.fetch(keys_only=True)) & set(
            q2.fetch(keys_only=True))
        )
```

This method can be invoked like this:
```python
    non_workshop = Session.query(
        Session.typeOfSession != 'WORKSHOP')
    before_seven = Session.query(
        Session.startTime < datetime.strptime("19:00", "%H:%M").time())

    sessions = self._intersectQueries(non_workshop,before_seven)
```

Besides the fact that the code has a re-usable component, an other advantage
(at least in my opinion) is easier to read.

For a lot of datasets this solution will work well enough. For really big
datasets a solution with the [MapReduce][9] library would probably give a
better solution. It's a more havyweight approach, yet more scalable.


## Task 4: Add a Task

When a new session is added to a conference, the schedule of its speakers is
checked. A schedule is is represented in a dictionary like:
```python
    {
        'name': <speaker_name>,
        'sessions': {
            <session_websafekey>: <session_name>,
            <session_websafekey>: <session_name>,
            ...
        }
    }
```

If a speaker is speaking at more than one session  at the same conference --
when the length of the embedded dictionary 'sessions' is bigger than one -- the
speaker is set as a featured speaker. Featured speakers will be safed in a
Memcache entry specific for the conference, which will be done by using App
Engine's Task Queue mechanism.
The key for such an entry is dynamically constructed with a constant prefix
followed by the conference's websafe key:
`FEATURED_SPEAKER_<conference_websafekey>`.
The entry itself holds a JSON representation of a dictionary with schedules of
the featured speakers in a conference, which looks like:
like:
```python
    {
        <speaker_websafekey>: <speaker_schedule>,
        ...
    }
```

This way the dictionary has (unique) websafe keys that could eventually be used
for querying, and human readable data to easily construct a sentence like
"Speaker X is featured speaker at the conference. The sessions he will be
speaking at are titled Y and Z."
The endpoint to check for featured speakers is `getFeaturedSpeaker()`, which
will search for an entry based on the websafe conferencekey given with the
request.


[1]: http://python.org
[2]: https://developers.google.com/appengine
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://localhost:8080/
[6]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
[7]: https://ud858conferencecentral.appspot.com/_ah/api/explorer
[8]: https://cloud.google.com/appengine/docs/python/ndb/queries
[9]: https://cloud.google.com/appengine/docs/python/dataprocessing/
