package main

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"io"
	"strings"
	"testing"
)

// These are owned source strings, never compiled/imported as upstream packages.
func ownedFile(name, text string) SourceFile {
	raw := []byte(text)
	return SourceFile{Name: name, Path: "tsc/internal/owned/" + name, SHA: digest(raw), Bytes: len(raw), Data: raw}
}

func ownedPackage(internal, external string) PackageInput {
	pkg := PackageInput{ImportPath: prefix + "/internal/owned", Dir: cwd + "/internal/owned", Name: "owned"}
	if internal != "" {
		pkg.TestGoFiles = []SourceFile{ownedFile("owned_test.go", internal)}
	}
	if external != "" {
		pkg.XTestGoFiles = []SourceFile{ownedFile("external_test.go", external)}
	}
	return pkg
}

func names(declarations []Declaration) string {
	values := []string{}
	for _, decl := range declarations {
		values = append(values, decl.Name)
	}
	return strings.Join(values, ",")
}

func TestDiscoveryNamesAndSignatures(t *testing.T) {
	cases := []struct {
		name, source, tests, benchmarks, fuzz string
		unresolved                            bool
	}{
		{"bare-prefix", "func Test(*testing.T) {}", "Test", "", "", false},
		{"uppercase", "func TestOwned(t *renamed.T) {}", "TestOwned", "", "", false},
		{"dot-import-shape", "func TestOwned(t *T) {}", "TestOwned", "", "", false},
		{"underscore", "func Test_owned(*testing.T) {}", "Test_owned", "", "", false},
		{"unicode-title", "func Testǅowned(*testing.T) {}", "Testǅowned", "", "", false},
		{"unicode-lower", "func Testéowned(*testing.T) {}", "", "", "", false},
		{"lower-prefix", "func Testicular(*testing.T) {}", "", "", "", false},
		{"receiver", "func (x *Thing) TestOwned(*testing.T) {}", "", "", "", false},
		{"string-and-comment", "var x = `func TestFake(*testing.T) {}`\n// func TestComment(*testing.T) {}", "", "", "", false},
		{"result", "func TestOwned(*testing.T) int { return 0 }", "", "", "", true},
		{"nonpointer", "func TestOwned(testing.T) {}", "", "", "", true},
		{"wrongtype", "func TestOwned(*testing.B) {}", "", "", "", true},
		{"two-params", "func TestOwned(t, u *testing.T) {}", "", "", "", true},
		{"generics", "func TestOwned[X any](*testing.T) {}", "", "", "", true},
		{"benchmark", "func BenchmarkOwned(*testing.B) {}", "", "BenchmarkOwned", "", false},
		{"fuzz", "func FuzzOwned(*testing.F) {}", "", "", "FuzzOwned", false},
		{"main-as-test", "func TestMain(*testing.T) {}", "TestMain", "", "", false},
		{"main-as-test-discovery-quirk", "func TestMain[X any](*testing.T) {}", "TestMain", "", "", false},
		{"main-wrapper", "func TestMain(*testing.M) {}", "", "", "", false},
		{"bad-main", "func TestMain() {}", "", "", "", true},
		{"parse-error", "func TestBroken( {", "", "", "", true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := discover(ownedPackage("package owned\n"+tc.source+"\n", ""))
			if names(got.Tests) != tc.tests || names(got.Benchmarks) != tc.benchmarks || names(got.FuzzTargets) != tc.fuzz || (len(got.Diagnostics) > 0) != tc.unresolved {
				t.Fatalf("unexpected registry: %+v", got)
			}
			if !got.CompileValidityUnestablished {
				t.Fatal("discovery must never assert compilation")
			}
			if tc.name == "main-wrapper" && len(got.TestMains) != 1 {
				t.Fatal("wrapper metadata missing")
			}
		})
	}
}

func TestExamplesUseOutputAndSourceOrder(t *testing.T) {
	source := "package owned\n" +
		"func ExampleZulu() {\n// Output: z\n}\n" +
		"func ExampleNone() {}\n" +
		"func ExampleEmpty() {\n// Output:\n}\n" +
		"func ExampleAlpha_suffix() {\n// Unordered output: b\n// a\n}\n" +
		"func ExampleParams(x int) {\n// Output: x\n}\n" +
		"func ExampleResult() int {\n// Output: x\nreturn 0\n}\n" +
		"func ExampleNotLast() {\n// Output: x\n//\n// unrelated\n}\n"
	got := discover(ownedPackage(source, ""))
	if names(got.Examples) != "ExampleZulu,ExampleEmpty,ExampleAlpha_suffix,ExampleNotLast" {
		t.Fatalf("order/output discovery: %+v", got.Examples)
	}
	if !got.Examples[1].EmptyOutput || !got.Examples[2].Unordered {
		t.Fatal("empty/unordered flags lost")
	}
	if !strings.Contains(got.Examples[3].Output, "unrelated") {
		t.Fatal("same output comment group must use Go doc semantics")
	}
	if len(got.Diagnostics) != 0 {
		t.Fatalf("unexpected diagnostics: %+v", got.Diagnostics)
	}
	// A separate last comment group which is not output makes the example unrunnable.
	other := discover(ownedPackage("package owned\nfunc ExampleWrong() {\n// Output: x\n\n// unrelated\n}\n", ""))
	if len(other.Examples) != 0 {
		t.Fatal("wrong output comment placement accepted")
	}
}

func TestDuplicatesRetainDistinctStableDeclarations(t *testing.T) {
	got := discover(ownedPackage("package owned\nfunc TestSame(*testing.T) {}\n", "package owned_test\nfunc TestSame(*testing.T) {}\n"))
	if len(got.Tests) != 2 || got.Tests[0].ID == got.Tests[1].ID || len(got.Diagnostics) != 1 || got.State != "unresolved-source-discovery" {
		t.Fatalf("duplicate disappeared: %+v", got)
	}
	again := discover(ownedPackage("package owned\nfunc TestSame(*testing.T) {}\n", "package owned_test\nfunc TestSame(*testing.T) {}\n"))
	if got.Tests[0].ID != again.Tests[0].ID || got.Tests[1].ID != again.Tests[1].ID {
		t.Fatal("unstable declaration IDs")
	}
	examples := discover(ownedPackage("package owned\nfunc ExampleSame() {\n// Output: a\n}\nfunc ExampleSame() {\n// Output: b\n}\n", ""))
	if len(examples.Examples) != 2 || examples.Examples[0].ID == examples.Examples[1].ID || len(examples.Diagnostics) == 0 {
		t.Fatalf("example duplicate discarded: %+v", examples)
	}
	mains := discover(ownedPackage("package owned\nfunc TestMain(*testing.M) {}\n", "package owned_test\nfunc TestMain(*testing.M) {}\n"))
	if len(mains.TestMains) != 2 || len(mains.Diagnostics) == 0 {
		t.Fatal("multiple wrappers accepted")
	}
}

func TestExternalPackageClauseAndEmptyRegistry(t *testing.T) {
	got := discover(ownedPackage("", "package wrong\nfunc TestOwned(*testing.T) {}\n"))
	if got.State != "unresolved-source-discovery" {
		t.Fatal("external clause mismatch accepted")
	}
	empty := discover(ownedPackage("", ""))
	if len(empty.Tests) != 0 || empty.State != "source-derived-uncompiled" {
		t.Fatal("empty registry invented tests")
	}
}

func TestPhysicalLocationIgnoresLineDirective(t *testing.T) {
	got := discover(ownedPackage("package owned\n//line invented.go:900\nfunc TestOwned(*testing.T) {}\n", ""))
	if len(got.Tests) != 1 || got.Tests[0].Line != 3 || got.Tests[0].SourcePath != "tsc/internal/owned/owned_test.go" {
		t.Fatalf("directive changed literal source locator: %+v", got)
	}
}

func TestBodylessExampleAndMethodAreNotRegistered(t *testing.T) {
	got := discover(ownedPackage("package owned\nfunc ExampleBodyless()\nfunc (x *Thing) ExampleMethod() {\n// Output: x\n}\n", ""))
	if len(got.Examples) != 0 || len(got.Diagnostics) != 0 {
		t.Fatalf("non-example registered: %+v", got)
	}
}

func TestJSONStructureRefusesAmbiguity(t *testing.T) {
	for _, raw := range []string{`{"schema":"x","schema":"y"}`, `{} {}`, `{"unknown":1}`, `{`} {
		if _, err := decodeInput([]byte(raw)); err == nil {
			t.Fatalf("invalid input accepted: %s", raw)
		}
	}
	// Decode enforces the closed production context; owned discovery tests above
	// deliberately bypass that boundary and cannot become real corpus output.
	if _, err := decodeInput([]byte(`{"schema":"go01-source-registry-input-v1","sourceContext":{},"packages":[]}`)); err == nil {
		t.Fatal("empty manifest accepted")
	}
	encoded, err := json.Marshal(ownedFile("owned_test.go", "package owned\n"))
	if err != nil || !strings.Contains(string(encoded), "dataBase64") {
		t.Fatal("source bytes encoding changed")
	}
}

func TestDeterministicBoundedGzipEncoding(t *testing.T) {
	out := Output{Schema: "owned-fixture", State: "source-derived-uncompiled", Packages: []PackageRegistry{discover(ownedPackage("package owned\nfunc TestOwned(*T) {}\n", ""))}, UniversalCompileValidityUnestablished: true}
	first, err := encodeOutput(out)
	if err != nil {
		t.Fatal(err)
	}
	second, err := encodeOutput(out)
	if err != nil || !bytes.Equal(first, second) {
		t.Fatal("nondeterministic gzip")
	}
	reader, err := gzip.NewReader(bytes.NewReader(first))
	if err != nil {
		t.Fatal(err)
	}
	if !reader.ModTime.IsZero() || reader.Name != "" || reader.Comment != "" || len(reader.Extra) != 0 || reader.OS != 255 {
		t.Fatal("unexpected gzip header")
	}
	raw, err := io.ReadAll(reader)
	if err != nil || reader.Close() != nil || len(raw) > maxExpandedOutput || !json.Valid(raw) {
		t.Fatal("invalid JSON member")
	}
	out.State = strings.Repeat("x", maxExpandedOutput)
	if wire, err := encodeOutput(out); err == nil || wire != nil {
		t.Fatal("oversized output emitted")
	}
}
