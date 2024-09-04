=========
hms-utils
=========

----------
Change Log
----------

1.2.0
=====
* 2024-09-04/dmichaels
  - Hooks to "import" additional/multiple config/secrets documents (JSON) into Config;
    may eventually just replace special handling of (single) secrets.

1.1.56
======

* 2024-08-30/dmichaels
* Initial checkin.
* Miscellaneous Python utilities.
  - hms-aws-env: Manage SSO-based AWS credentials in ~/.aws/config.
  - hms-aws-ecs: View AWS ECS info.
  - hms-config: Manage local/dev config/secrets properties/value in ~/.config/hms/{config,secrets}.json.
