# Changelog

## [0.5.5](https://github.com/allenanswerzq/fava-envelope/compare/v0.5.4...v0.5.5) (2024-08-03)


### Bug Fixes

* [#34](https://github.com/allenanswerzq/fava-envelope/issues/34) remove unused line in example ([d88d52c](https://github.com/allenanswerzq/fava-envelope/commit/d88d52c8e303a3ea5af9f23535c552d3632d9692))
* bug where it would not load page for month selected ([ab039aa](https://github.com/allenanswerzq/fava-envelope/commit/ab039aa2787fd75c8873f11e39de1c95977ec7dc))
* bug where tables were not displaying on the latest fava ([68e1981](https://github.com/allenanswerzq/fava-envelope/commit/68e19810abaa6ba09c7f40d8c4b28eb39fee53bb))
* nix to use poetry2nix ([e972bec](https://github.com/allenanswerzq/fava-envelope/commit/e972bec9fdcfcebbdd20891e809867362047872c))
* publish script ([9eac51e](https://github.com/allenanswerzq/fava-envelope/commit/9eac51ed90e1eda9eaa5276f865db3c06044b93c))
* replace url_for_current with url_for (for compatibility with fava 1.20 and up) ([910b3ad](https://github.com/allenanswerzq/fava-envelope/commit/910b3ad742683e747660c09430e56415ee44d8c3))
* security dependency updates ([3e8d4b6](https://github.com/allenanswerzq/fava-envelope/commit/3e8d4b6f3cf47725c70e4ed4a703139c4fa4f073))
* typo ([f4be2d2](https://github.com/allenanswerzq/fava-envelope/commit/f4be2d2bb83b49c1a3dc03c8403365181cdd19a6))


### Documentation

* changlog edits ([fe6fc3a](https://github.com/allenanswerzq/fava-envelope/commit/fe6fc3a3dba23fcdffad5f0eb1822496afe371b3))
* changlog edits ([c1e59e0](https://github.com/allenanswerzq/fava-envelope/commit/c1e59e0bbe9f6640a793610bf5a7aac1a0be7d1c))

### [0.5.4](https://github.com/polarmutex/fava-envelope/compare/v0.5.3...v0.5.4) (2022-05-19)


### Bug Fixes

* [#34](https://github.com/polarmutex/fava-envelope/issues/34) remove unused line in example ([d88d52c](https://github.com/polarmutex/fava-envelope/commit/d88d52c8e303a3ea5af9f23535c552d3632d9692))
* security dependency updates ([3e8d4b6](https://github.com/polarmutex/fava-envelope/commit/3e8d4b6f3cf47725c70e4ed4a703139c4fa4f073))


### Documentation

* changlog edits ([fe6fc3a](https://github.com/polarmutex/fava-envelope/commit/fe6fc3a3dba23fcdffad5f0eb1822496afe371b3))
* changlog edits ([c1e59e0](https://github.com/polarmutex/fava-envelope/commit/c1e59e0bbe9f6640a793610bf5a7aac1a0be7d1c))

### [0.5.3](https://github.com/polarmutex/fava-envelope/compare/v0.5.2...v0.5.3) (2022-05-19)

### Features

* Added negative rollover option
* Add rudimentary ability to see future months

### Bug Fixes

* replace url_for_current with url_for (for compatibility with fava 1.20 and up) ([910b3ad](https://github.com/polarmutex/fava-envelope/commit/910b3ad742683e747660c09430e56415ee44d8c3))

### [0.5.2](https://github.com/polarmutex/fava-envelope/compare/v0.5.1...v0.5.2) (2021-07-19)

### Bug Fixes

* bug where tables were not displaying on the latest fava

### [0.5.1](https://github.com/polarmutex/fava-envelope/compare/0.5...v0.5.1) (2021-01-29)

### Features

* Adding multiple budgets in multiple currencies capacity to fava_envelope

### Bug Fixes

* bug where it would not load page for month selected
* add checks for lastest fava which changed querytable api
* Fixed a typo in get_currencies()
* probably should not hard code 2020
* allow months with no income by setting the default to 0
* use beancounts operating_currency if available
