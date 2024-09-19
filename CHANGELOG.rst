======================
hms-utils : CHANGE LOG
======================

1.2.72
======
* 2024-09-11/dmichaels
  - Using new dictionary_utils.JSON for parent-award dictionary.
    Previous commit not doing this: fb97104389cd6d2d0123b835ee4381cbfb3e6dee

1.2.56
======
* 2024-09-09/dmichaels
  - Added GitHub support to hms-aws-ecs to get git commit date and latest commit.

1.2.44
======
* 2024-09-09/dmichaels
  - Working on better lookup for exports of dictionary in hms-config.
  - New hms-portal-indexing-status script.

1.2.40
======
* 2024-09-08/dmichaels
  - More info output for hms-aws-ecs.

1.2.37
======
* 2024-09-07/dmichaels
  - Support for ${aws-secret:SECRET_NAME} in hms-config.
  - Prior commit: 5848245559326fc40443144519fc5320e9b9bb65

1.2.26
======
* 2024-09-07/dmichaels
  - Added async capability to hms-aws-env for a bit faster response.

1.2.20
======
* 2024-09-06/dmichaels
  - Got identity-swap preview working for 4dn style swapping in hms-aws-env.

1.2.11
======
* 2024-09-05/dmichaels
  - Improvements with more info to hms-aws-env.

1.2.2
=====
* 2024-09-04/dmichaels
  - Hooks to "import" for hms-config additional/multiple config/secrets documents
    into Config; may eventually just replace special handling of (single) secrets.

1.1.56
======

* 2024-08-30/dmichaels
* Initial checkin.
* Miscellaneous Python utilities.
  - hms-aws-env: Manage SSO-based AWS credentials in ~/.aws/config.
  - hms-aws-ecs: View AWS ECS info.
  - hms-config: Manage local/dev config/secrets properties/value in ~/.config/hms/{config,secrets}.json.
