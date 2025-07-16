# Changelog

## 0.4.0

- Added dependency to [SUOU](https://github.com/sakuragasaki46/suou) library
- Users can now block each other
    + Blocking a user prevents them from seeing your comments, posts (standalone or in feed) and profile
- Added user strikes: a strike logs the content of a removed message for future use
- Posts may now be deleted by author. If it has comments, comments are not spared
- Moderators (and admins) have now access to mod tools
    + Allowed operations: change display name, description, restriction status, and exile (guild-local ban) members
    + Site administrators and guild owners can add moderators
- Administrators can claim ownership of abandoned guilds
- Implemented guild subscriptions (not as in $$$, yes as in the follow button)
- Added ✨color themes✨
- Users can now set their display name, biography and color theme in `/settings`
- You can now add an impressum in .env, e.g. `IMPRESSUM='Acme Ltd.::1 Short Island::Old York, Divided States::Responsible: ::Donald Duck'` Lines are separated by two colons. Version before 0.4.0 CAN'T BE RUN in German-speaking countries as of 2025.

## 0.3.3

- Fixed bugs in templates introduced in 0.3.2
- Improved karma management
- Fixed og: meta tags missing 

## 0.3.2

- Fixed administrator users not being able to create +guilds

## 0.3.1

- Fixed a critical bug that prevented database initialization

## 0.3.0

- Initial commit
- Post and read comments on posts
- Public timeline
- Create +guilds
- Reporting
- Edit own posts
- Admins can remove reported posts
- Upvotes and downvotes

## 0.2 and earlier

*Releases before 0.3.0 are lost for good, and for a good reason.*

