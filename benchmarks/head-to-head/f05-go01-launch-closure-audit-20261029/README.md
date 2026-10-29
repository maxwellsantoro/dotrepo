# Bounded Go01 launch-closure source audit

The exact b47 never-started image export remains locally retained. Its complete
1.937GB archive SHA was rechecked; selected installed npm11.19.1 source matches
the frozen image inventory. No acquisition, daemon, package import or execution
was needed. Selected Hereby1.15.2/tinyexec1.3.1 and three hook packages are read
from SHA512-lock-verified cached blobs. Raw source copies preserve all bytes.

The selected route is now source-traced: image shell wrappers call PATH-resolved
node; npx rewrites to npm exec; config exports env (including NODE_OPTIONS);
run-script and tinyexec each prepend ancestor .bin paths; Hereby reexecs its local
package, chdirs and imports modules before selecting full test:tsc; the source-
owned gotestsum ensure either reuses cache or awaits a build and writes its hash.

A useful additional source/data input is tools/scripts/tsc/ast.json: schema.ts
reads/validates it at module load even when no generator task was chosen. That is
not a reason to execute every imported generator body. Normal hooks have real
optional-package and fallback/copy/bin-rewrite branches; npm exit0 and banners
do not establish which branch ran in a later session.

`route-map.json` separates inspected conditional transformations from uninspected
initializer/config/installed-state frontiers. `source-spans.json` gives exact
file/hash/line locators; `report.json` records the four prospective input gates.
Current runtime allowed env keys also do not automatically supply the explicit
target Go settings assumed in a different collection epoch. No env injection
solely for witnessing is proposed. A finite current-tree witness must catch new
selected Go files and fixture changes, not rehash only an old Go-path subset.

The source audit does not close actual parent/child environment or full launch
closure. Further bounded source/observation decisions or the plan's separately
reviewed actual Hereby-parent witness remain necessary. No new tracer/platform,
new skip policy, task change, resource increase or admission is proposed. All
actual flags remain false. Data-reader scripts are retained as authoring receipts;
they create source copies exclusively and should not be rerun over this freeze.
