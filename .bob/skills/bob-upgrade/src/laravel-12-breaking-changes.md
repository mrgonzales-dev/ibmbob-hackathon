# Laravel 11 to 12 Breaking Changes

Source of truth: <https://laravel.com/docs/12.x/upgrade>

Every row below comes from the official upgrade guide. The `Impact` column
copies the rating Laravel publishes. Do not add a row from memory.

When you find a code signal with no row here, fetch the upgrade guide and
report the result with its URL. Never report a finding that you did not read
in the guide or in this file.

## How impact maps to severity

| Impact rating | Report severity | Reason |
|---|---|---|
| High | HIGH | The upgrade fails or the test suite fails. |
| Medium | MED | The code runs but produces wrong data. |
| Low | LOW | The code runs. Behaviour differs from before. |
| Very Low | LOW | The change affects package authors more than applications. |

## Dependency changes

| ID | Change | Impact | Detect signal | Fix |
|---|---|---|---|---|
| DEP-001 | `laravel/framework` must be `^12.0` | High | `composer.json` `require` has `laravel/framework` below `^12.0` | Set the constraint to `^12.0`. |
| DEP-002 | `phpunit/phpunit` must be `^11.0` | High | `composer.json` `require-dev` has `phpunit/phpunit` below `^11.0` | Set the constraint to `^11.0`. |
| DEP-003 | `pestphp/pest` must be `^3.0` | High | `composer.json` `require-dev` has `pestphp/pest` below `^3.0` | Set the constraint to `^3.0`. |
| API-003 | Carbon 2 support removed. Carbon 3 is required | Low | `nesbot/carbon` is `2.x` in `composer.lock` or `composer.json` | Update Carbon to `^3.0`. |

## Model and identifier changes

| ID | Change | Impact | Detect signal | Fix |
|---|---|---|---|---|
| API-001 | The `HasVersion7Uuids` trait was removed | Medium | `HasVersion7Uuids` appears in any file | Replace it with `HasUuids`. |
| API-002 | `HasUuids` now returns UUID version 7 | Medium | `HasUuids` appears in any file | Use `HasVersion4Uuids` to keep version 4 identifiers. |

## Container, concurrency, and authentication

| ID | Change | Impact | Detect signal | Fix |
|---|---|---|---|---|
| API-005 | `Concurrency::run` now returns results under their array keys | Low | `Concurrency::run(` with an array argument | Read results by key. Remove any index assumption. |
| API-006 | The container uses default class property values on resolve | Low | `resolve(` with a class argument | Accept the new default. Adjust code that assumed no default. |
| API-004 | `DatabaseTokenRepository` reads `$expires` in seconds | Very Low | `DatabaseTokenRepository` appears in any file | Multiply minutes by 60. |

## Request and validation changes

| ID | Change | Impact | Detect signal | Fix |
|---|---|---|---|---|
| API-007 | The `image` rule rejects SVG files | Low | A validation rule contains `image` and no `allow_svg` | Add `image:allow_svg` or `File::image(allowSvg: true)`. |
| API-008 | `mergeIfMissing` now merges nested keys in dot notation | Low | `mergeIfMissing(` with a dotted array key | Read the nested value. Remove the flat key expectation. |

## Storage and routing changes

| ID | Change | Impact | Detect signal | Fix |
|---|---|---|---|---|
| CFG-001 | The `local` disk root defaults to `storage/app/private` | Low | `config/filesystems.php` has no `local` key in `disks`, and code calls `Storage::disk('local')` | Define the `local` disk with root `storage/app`, or move reads. |
| API-009 | Duplicate route names match the first registration | Low | The same `->name(` value appears on two routes | Rename one route. |

## Database and schema changes

| ID | Change | Impact | Detect signal | Fix |
|---|---|---|---|---|
| DB-001 | `getTables`, `getViews`, and `getTypes` span all schemas | Low | `getTables(`, `getViews(`, or `getTypes(` appears | Pass the `schema` argument to limit results. |
| DB-002 | `getTableListing` returns schema-qualified names | Low | `getTableListing(` appears | Pass `schemaQualified: false` to keep short names. |
| DB-003 | The `Blueprint` constructor requires a `Connection` | Very Low | `new Blueprint(` appears | Pass the connection as the first argument. |
| DB-004 | `Grammar::setConnection` was removed | Very Low | `setConnection(` appears on a grammar object | Pass the connection to the constructor. |
| DB-005 | `Blueprint::getPrefix` is deprecated | Very Low | `getPrefix(` appears | Read the prefix from the connection. |
| DB-006 | `Connection::withTablePrefix` was removed | Very Low | `withTablePrefix(` appears | Read the prefix from the connection. |

## Rules the scanner cannot decide alone

These two rules need a read of the whole file. The scanner never reports them.
Read them by hand and mark each row as a heuristic match.

| ID | Why the scanner skips it |
|---|---|
| API-007 | The rule needs both the `image` keyword and the absence of `allow_svg` on the same chain. |
| API-009 | The rule needs the same `->name(` value on two different routes. |

## Remediation code

### API-001 and API-002, identifier traits

```php
// Laravel 11
use Illuminate\Database\Eloquent\Concerns\HasVersion7Uuids;
use Illuminate\Database\Eloquent\Concerns\HasUuids;

// Laravel 12
use Illuminate\Database\Eloquent\Concerns\HasUuids;
```

```php
// Laravel 12, to keep version 4 identifiers
use Illuminate\Database\Eloquent\Concerns\HasVersion4Uuids as HasUuids;
```

### API-003, Carbon

```json
{
    "require": {
        "nesbot/carbon": "^3.0"
    }
}
```

### API-007, image validation

```php
// Laravel 11
'photo' => ['required', 'image'],

// Laravel 12, to allow SVG
'photo' => ['required', 'image:allow_svg'],
'photo' => ['required', Illuminate\Validation\Rules\File::image(allowSvg: true)],
```

### API-008, nested merge

```php
// Laravel 11, flat key
$request->mergeIfMissing(['user.last_name' => 'Otwell']);
// $request->input('user.last_name') is null

// Laravel 12, nested value
$request->mergeIfMissing(['user.last_name' => 'Otwell']);
// $request->input('user')['last_name'] is 'Otwell'
```

### CFG-001, the local disk

```php
// config/filesystems.php
'disks' => [
    'local' => [
        'driver' => 'local',
        'root' => storage_path('app'),
        'throw' => false,
    ],
],
```

### DB-003 and DB-004, schema builders

```php
// Laravel 11
$grammar = new MySqlGrammar;
$grammar->setConnection($connection);
$blueprint = new Blueprint('shifts');

// Laravel 12
$grammar = new MySqlGrammar($connection);
$blueprint = new Blueprint('shifts', $connection);
```

## What the upgrade guide does not change

Do not report these. The guide lists no change for them.

| Claim | Status |
|---|---|
| `Str::camel` trims leading underscores | No change in Laravel 12. |
| `Route::pattern` behaves differently for optional segments | No change in Laravel 12. |
| `Schema::table` column order differs | No change in Laravel 12. |
| `config/queue.php` default connection changed to `database` | The `laravel/laravel` skeleton changed. The framework did not. |
| `config/app.php` `aliases` array was restructured | The `laravel/laravel` skeleton changed. The framework did not. |
| The `auth` guard driver `token` was deprecated | The driver was removed in Laravel 5.2. |
| `spatie/laravel-permission` below `^6.0` breaks on Laravel 12 | The guide states no such rule. Check the package changelog. |
| `laravel/sanctum` below `^4.0` is unsupported | The guide states no such rule. Check the package changelog. |
