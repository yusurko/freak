# Changelog

## 0.5.0

- Switched to Quart framework. This implies everything is `async def` now.
- **BREAKING**: `SERVER_NAME` env variable now contains the domain name. `DOMAIN_NAME` has been removed.
- libsuou bumped to 0.6.0
- Added several REST routes. Change needed due to pending [frontend separation](https://nekode.yusur.moe/yusur/vigil).
- Deprecated the old web routes except for `/report` and `/admin`

## 0.4.0

- Added dependency to [SUOU](https://github.com/yusurko/suou) library
- Users can now block each other
    + Blocking a user prevents them from seeing your comments, posts (standalone or in feed) and profile
- Added user strikes: a strike logs the content of a removed message for future use
- Added ✨**color themes**✨
- Posts may now be deleted by author. If it has comments, comments are not spared
- If a user for some reason can't post, their post is blocked and they can choose to post it onto another community. Previously it got posted to the user page.
- Moderators (and admins) have now access to mod tools
    + Allowed operations: change display name, description, restriction status, and exile (guild-local ban) members
    + Site administrators and guild owners can add moderators
- Guilds can have restricted posting/commenting now. Unmoderated guilds always have
- Administrators can claim ownership of abandoned guilds
- Admins can now suspend users from admin panel
- Implemented guild subscriptions (not as in $$$, yes as in the follow button)
- Minimum karma requirement for creating a guild is now configurable via env variable `FREAK_CREATE_GUILD_THRESHOLD` (previously hardcoded at 15)
- Users can now set their display name, biography and color theme in `/settings`
- Impressum can now be set in .env, e.g. `IMPRESSUM='Acme Ltd.::1 Short Island::Old York, Divided States::Responsible: ::Donald Duck'` Lines are separated by two colons. **Versions before 0.4.0 CAN'T BE RUN in German-speaking countries** as of 2025
- Several aesthetic improvements

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

