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
The following endpoint methods have been defined:
1. getConferenceSessions(websafeConferenceKey) -- This invokes a generic _getSessions method which returns a list of existing Sessions of a conference that matches the given webSafeConferenceKey.
1. getConferenceSessionsByType(websafeConferenceKey, typeofSession) -- This invokes a generic _getSessions method which returns a limited list of existing Sessions of a conference that matches the given webSafeConferenceKey. Because in this case the invokation of the generic _getSessions method is done with an extra parameter for filtering on type, it will limit the list Sessions according to the given type.
1. getSessionsBySpeaker(speaker) -- This method returns a list of Sessions accross all conferences, limited to the Sessions where the given speaker is in the list of speakers.
1. createSession(SessionForm, websafeConferenceKey) -- This invokes a _createSessionObject method which copies the data from the request to a new Session object.

[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://localhost:8080/
[6]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
