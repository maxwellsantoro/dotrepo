// Source-only experiment. No upstream imports, type checking, generation or execution.
// Discovery predicates adapted from Go cmd/go/internal/load/test.go:
// Copyright 2018 The Go Authors. All rights reserved.
// See GO-LICENSE for the BSD-style license governing those portions.
package main

import (
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"go/ast"
	"go/doc"
	"go/parser"
	"go/token"
	"io"
	"os"
	"path"
	"runtime"
	"sort"
	"strings"
	"unicode"
	"unicode/utf8"
)

const maxInput = 32 << 20
const maxSelected = 24 << 20
const maxFile = 8 << 20
const maxExpandedOutput = 8 << 20
const maxCompressedOutput = 2 << 20
const prefix = "github.com/microsoft/TypeScript/tsc"
const cwd = "/workspace/repository/tsc"
const schema = "go01-source-registry-input-v1"

type Context struct {
	Repository          string `json:"repository"`
	Revision            string `json:"revision"`
	ImageID             string `json:"imageId"`
	GoVersion           string `json:"goVersion"`
	SourceArchiveSHA    string `json:"sourceArchiveSha256"`
	SourceInventorySHA  string `json:"sourceInventorySha256"`
	PackageInventorySHA string `json:"packageInventorySha256"`
	EnvironmentSHA      string `json:"environmentSha256"`
	DiscoverySourcesSHA string `json:"discoverySourcesSha256"`
	SelectionSHA        string `json:"selectionSha256"`
}

type SourceFile struct {
	Name  string `json:"name"`
	Path  string `json:"path"`
	SHA   string `json:"sha256"`
	Bytes int    `json:"bytes"`
	Data  []byte `json:"dataBase64"`
}

type PackageInput struct {
	ImportPath   string       `json:"importPath"`
	Dir          string       `json:"dir"`
	Name         string       `json:"name"`
	TestGoFiles  []SourceFile `json:"testGoFiles"`
	XTestGoFiles []SourceFile `json:"xTestGoFiles"`
}

type Input struct {
	Schema   string         `json:"schema"`
	Context  Context        `json:"sourceContext"`
	Packages []PackageInput `json:"packages"`
}

type Declaration struct {
	ID          string `json:"id"`
	Kind        string `json:"kind"`
	Name        string `json:"name"`
	SourcePath  string `json:"sourcePath"`
	SourceSHA   string `json:"sourceSha256"`
	PackageRole string `json:"packageRole"`
	Line        int    `json:"line"`
	Column      int    `json:"column"`
	Offset      int    `json:"offset"`
	EndOffset   int    `json:"endOffset"`
	Output      string `json:"output,omitempty"`
	EmptyOutput bool   `json:"emptyOutput,omitempty"`
	Unordered   bool   `json:"unordered,omitempty"`
}

type Diagnostic struct {
	Code       string `json:"code"`
	SourcePath string `json:"sourcePath,omitempty"`
	Message    string `json:"message"`
}

type PackageRegistry struct {
	ImportPath                   string        `json:"importPath"`
	Tests                        []Declaration `json:"tests"`
	Benchmarks                   []Declaration `json:"benchmarks"`
	FuzzTargets                  []Declaration `json:"fuzzTargets"`
	Examples                     []Declaration `json:"examples"`
	TestMains                    []Declaration `json:"testMains"`
	Diagnostics                  []Diagnostic  `json:"diagnostics"`
	State                        string        `json:"state"`
	CompileValidityUnestablished bool          `json:"compileValidityUnestablished"`
}

type Output struct {
	Schema                                string            `json:"schema"`
	State                                 string            `json:"state"`
	SourceContext                         Context           `json:"sourceContext"`
	HelperGoVersion                       string            `json:"helperGoVersion"`
	HelperGOOS                            string            `json:"helperGOOS"`
	HelperGOARCH                          string            `json:"helperGOARCH"`
	InputSHA                              string            `json:"inputSha256"`
	Packages                              []PackageRegistry `json:"packages"`
	UniversalCompileValidityUnestablished bool              `json:"universalCompileValidityUnestablished"`
	NativeCollectionOccurred              bool              `json:"nativeCollectionOccurred"`
	TaskOutcomeObserved                   bool              `json:"taskOutcomeObserved"`
}

func digest(raw []byte) string {
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

func hashShape(value string) bool {
	decoded, err := hex.DecodeString(value)
	return err == nil && len(decoded) == 32 && value == strings.ToLower(value)
}

func safePath(value string) bool {
	if value == "" || strings.ContainsAny(value, "\\:") {
		return false
	}
	for _, part := range strings.Split(strings.TrimPrefix(value, "/"), "/") {
		if part == "" || part == "." || part == ".." {
			return false
		}
	}
	for _, r := range value {
		if unicode.IsSpace(r) || unicode.IsControl(r) {
			return false
		}
	}
	return true
}

// Reject duplicate object keys before encoding/json's struct decoding can discard them.
func jsonShape(decoder *json.Decoder, depth int, tokens *int) error {
	*tokens++
	if depth > 12 || *tokens > 200000 {
		return fmt.Errorf("JSON structural bound")
	}
	tok, err := decoder.Token()
	if err != nil {
		return err
	}
	delim, ok := tok.(json.Delim)
	if !ok {
		return nil
	}
	switch delim {
	case '{':
		seen := map[string]bool{}
		for decoder.More() {
			key, err := decoder.Token()
			if err != nil {
				return err
			}
			name, ok := key.(string)
			if !ok || seen[name] {
				return fmt.Errorf("duplicate/invalid JSON key")
			}
			seen[name] = true
			if err := jsonShape(decoder, depth+1, tokens); err != nil {
				return err
			}
		}
	case '[':
		for decoder.More() {
			if err := jsonShape(decoder, depth+1, tokens); err != nil {
				return err
			}
		}
	default:
		return fmt.Errorf("invalid JSON delimiter")
	}
	_, err = decoder.Token()
	return err
}

func decodeInput(raw []byte) (Input, error) {
	var input Input
	if len(raw) == 0 || len(raw) > maxInput {
		return input, fmt.Errorf("input byte bound")
	}
	shape := json.NewDecoder(bytes.NewReader(raw))
	tokens := 0
	if err := jsonShape(shape, 0, &tokens); err != nil {
		return input, err
	}
	if _, err := shape.Token(); err != io.EOF {
		return input, fmt.Errorf("multiple/trailing JSON values")
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&input); err != nil {
		return input, err
	}
	if input.Schema != schema || len(input.Packages) != 104 {
		return input, fmt.Errorf("schema/package set shape")
	}
	c := input.Context
	if c.Repository != "github.com/microsoft/TypeScript" || c.Revision != "25f823dc198a00744b458a7bc6984359f0dd7cac" || c.GoVersion != "go1.27.3" || c.ImageID != "sha256:b47cd4a5061d271780bab25aa2637c2623dc675bd43380fc80cb65ec44e50092" || c.SourceArchiveSHA != "c583f28324d455b559bb232e7a280581fe874850f805decfb5947febfa91ee0f" {
		return input, fmt.Errorf("source context mismatch")
	}
	for _, value := range []string{c.SourceInventorySHA, c.PackageInventorySHA, c.EnvironmentSHA, c.DiscoverySourcesSHA} {
		if !hashShape(value) {
			return input, fmt.Errorf("source context digest shape")
		}
	}
	if c.SourceInventorySHA != "96c935c31228fa8e05bb836a93257beeb87ac524e5eb30cdde3c546a1ea4be0e" || c.PackageInventorySHA != "764fa272f1c461f4ecc2d6e2b58d641cc65c8e64da23f55981fa12b70c75bc21" || c.EnvironmentSHA != "3649e45b9b1c1f62faeb2c3a168d93d91a7be7a62e7e2905c07d9ba69ddb65fe" || c.DiscoverySourcesSHA != "4ff48c80f3ab60084de6e73563a5eae55227be5db1b34aa04e3e5a5ceba3efcb" {
		return input, fmt.Errorf("changed frozen source context")
	}
	count, total, previous := 0, 0, ""
	selection := bytes.NewBufferString("go01-selected-sources-v1\x00")
	for _, pkg := range input.Packages {
		if pkg.ImportPath <= previous || !safePath(pkg.ImportPath) || !safePath(pkg.Dir) || (pkg.ImportPath != prefix && !strings.HasPrefix(pkg.ImportPath, prefix+"/")) || pkg.Dir != cwd+strings.TrimPrefix(pkg.ImportPath, prefix) || !token.IsIdentifier(pkg.Name) {
			return input, fmt.Errorf("package identity/order")
		}
		previous = pkg.ImportPath
		fmt.Fprintf(selection, "P\x00%s\x00%s\x00%s\x00", pkg.ImportPath, pkg.Dir, pkg.Name)
		seen := map[string]bool{}
		for index, files := range [][]SourceFile{pkg.TestGoFiles, pkg.XTestGoFiles} {
			field := "testGoFiles"
			if index == 1 {
				field = "xTestGoFiles"
			}
			fmt.Fprintf(selection, "G\x00%s\x00", field)
			for _, file := range files {
				count++
				total += len(file.Data)
				if count > 6000 || total > maxSelected || len(file.Data) > maxFile || file.Bytes != len(file.Data) || !strings.HasSuffix(file.Name, "_test.go") || file.Name != path.Base(file.Name) || strings.ContainsAny(file.Name, "\\:") || file.Path != strings.TrimPrefix(pkg.Dir, "/workspace/repository/")+"/"+file.Name || seen[file.Path] || digest(file.Data) != file.SHA || !utf8.Valid(file.Data) {
					return input, fmt.Errorf("selected source shape/hash/bounds")
				}
				for _, r := range file.Name {
					if unicode.IsControl(r) || unicode.IsSpace(r) {
						return input, fmt.Errorf("source filename control/space")
					}
				}
				seen[file.Path] = true
				fmt.Fprintf(selection, "F\x00%s\x00%s\x00%d\x00", file.Path, file.SHA, file.Bytes)
			}
		}
	}
	if count != 4589 || total != 15262944 || input.Context.SelectionSHA != "3991848e78c757487dbe9146e7888db3dabe180bd5a9d353269855177266e308" || digest(selection.Bytes()) != input.Context.SelectionSHA {
		return input, fmt.Errorf("selected source inventory differs from closed corpus")
	}
	return input, nil
}

// Mirrors the discovery predicates in frozen cmd/go/internal/load/test.go:587-622.
func isTestFunc(fn *ast.FuncDecl, arg string) bool {
	if fn.Type.Results != nil && len(fn.Type.Results.List) > 0 || fn.Type.Params.List == nil || len(fn.Type.Params.List) != 1 || len(fn.Type.Params.List[0].Names) > 1 {
		return false
	}
	ptr, ok := fn.Type.Params.List[0].Type.(*ast.StarExpr)
	if !ok {
		return false
	}
	if name, ok := ptr.X.(*ast.Ident); ok && name.Name == arg {
		return true
	}
	if sel, ok := ptr.X.(*ast.SelectorExpr); ok && sel.Sel.Name == arg {
		return true
	}
	return false
}

func isTest(name, prefix string) bool {
	if !strings.HasPrefix(name, prefix) {
		return false
	}
	if len(name) == len(prefix) {
		return true
	}
	r, _ := utf8.DecodeRuneInString(name[len(prefix):])
	return !unicode.IsLower(r)
}

func checkTestFunc(fn *ast.FuncDecl, arg string) bool {
	return isTestFunc(fn, arg) && fn.Type.TypeParams.NumFields() == 0
}

func declaration(fset *token.FileSet, pkg string, file SourceFile, role, kind, name string, node *ast.FuncDecl) Declaration {
	pos, end := fset.PositionFor(node.Pos(), false), fset.PositionFor(node.End(), false)
	id := digest([]byte(strings.Join([]string{pkg, file.Path, file.SHA, role, kind, name, fmt.Sprint(pos.Offset)}, "\x00")))
	return Declaration{ID: id, Kind: kind, Name: name, SourcePath: file.Path, SourceSHA: file.SHA, PackageRole: role, Line: pos.Line, Column: pos.Column, Offset: pos.Offset, EndOffset: end.Offset}
}

func discover(pkg PackageInput) PackageRegistry {
	out := PackageRegistry{ImportPath: pkg.ImportPath, Tests: []Declaration{}, Benchmarks: []Declaration{}, FuzzTargets: []Declaration{}, Examples: []Declaration{}, TestMains: []Declaration{}, Diagnostics: []Diagnostic{}, State: "source-derived-uncompiled", CompileValidityUnestablished: true}
	fset := token.NewFileSet()
	for index, files := range [][]SourceFile{pkg.TestGoFiles, pkg.XTestGoFiles} {
		role := "internal"
		if index == 1 {
			role = "external"
		}
		for _, file := range files {
			f, err := parser.ParseFile(fset, file.Path, file.Data, parser.ParseComments|parser.SkipObjectResolution)
			if err != nil {
				out.Diagnostics = append(out.Diagnostics, Diagnostic{"parse-error", file.Path, err.Error()})
				continue
			}
			expectedPackage := pkg.Name
			if index == 1 {
				expectedPackage += "_test"
			}
			if f.Name.Name != expectedPackage {
				out.Diagnostics = append(out.Diagnostics, Diagnostic{"package-clause-mismatch", file.Path, f.Name.Name})
				continue
			}
			exampleFunctions := []*ast.FuncDecl{}
			for _, node := range f.Decls {
				fn, ok := node.(*ast.FuncDecl)
				if !ok || fn.Recv != nil {
					continue
				}
				if isTest(fn.Name.Name, "Example") && len(fn.Type.Params.List) == 0 && (fn.Type.Results == nil || len(fn.Type.Results.List) == 0) && fn.Body != nil {
					exampleFunctions = append(exampleFunctions, fn)
				}
				name, kind, arg := fn.Name.Name, "", ""
				switch {
				case name == "TestMain":
					if isTestFunc(fn, "T") {
						kind, arg = "test", "T"
					} else {
						kind, arg = "testMain", "M"
					}
				case isTest(name, "Test"):
					kind, arg = "test", "T"
				case isTest(name, "Benchmark"):
					kind, arg = "benchmark", "B"
				case isTest(name, "Fuzz"):
					kind, arg = "fuzz", "F"
				default:
					continue
				}
				// The frozen TestMain(*T) branch bypasses checkTestFunc; preserve that
				// discovery behavior while never claiming compilation/type validity.
				valid := checkTestFunc(fn, arg)
				if name == "TestMain" && kind == "test" {
					valid = isTestFunc(fn, "T")
				}
				decl := declaration(fset, pkg.ImportPath, file, role, kind, name, fn)
				if !valid {
					out.Diagnostics = append(out.Diagnostics, Diagnostic{"invalid-discovery-signature", file.Path, name})
					continue
				}
				switch kind {
				case "test":
					out.Tests = append(out.Tests, decl)
				case "benchmark":
					out.Benchmarks = append(out.Benchmarks, decl)
				case "fuzz":
					out.FuzzTargets = append(out.FuzzTargets, decl)
				case "testMain":
					out.TestMains = append(out.TestMains, decl)
				}
			}
			examples := doc.Examples(f)
			sort.Slice(examples, func(i, j int) bool { return examples[i].Order < examples[j].Order })
			for _, ex := range examples {
				if ex.Output == "" && !ex.EmptyOutput {
					continue
				}
				name := "Example" + ex.Name
				if ex.Order < 0 || ex.Order >= len(exampleFunctions) || exampleFunctions[ex.Order].Name.Name != name {
					out.Diagnostics = append(out.Diagnostics, Diagnostic{"example-location-unresolved", file.Path, name})
					continue
				}
				fn := exampleFunctions[ex.Order]
				decl := declaration(fset, pkg.ImportPath, file, role, "example", name, fn)
				decl.Output, decl.EmptyOutput, decl.Unordered = ex.Output, ex.EmptyOutput, ex.Unordered
				out.Examples = append(out.Examples, decl)
			}
		}
	}
	seen := map[string]bool{}
	for _, group := range [][]Declaration{out.Tests, out.Benchmarks, out.FuzzTargets, out.Examples} {
		for _, decl := range group {
			key := decl.Kind + "\x00" + decl.Name
			if seen[key] {
				out.Diagnostics = append(out.Diagnostics, Diagnostic{"duplicate-runtime-name-unresolved", decl.SourcePath, decl.Name})
			}
			seen[key] = true
		}
	}
	if len(out.TestMains) > 1 {
		out.Diagnostics = append(out.Diagnostics, Diagnostic{"multiple-testmain-unresolved", "", "multiple wrapper declarations"})
	}
	if len(out.Diagnostics) > 0 {
		out.State = "unresolved-source-discovery"
	}
	return out
}

func run(raw []byte) (Output, error) {
	input, err := decodeInput(raw)
	if err != nil {
		return Output{}, err
	}
	out := Output{Schema: "go01-source-registry-output-v1", State: "source-derived-uncompiled", SourceContext: input.Context, HelperGoVersion: runtime.Version(), HelperGOOS: runtime.GOOS, HelperGOARCH: runtime.GOARCH, InputSHA: digest(raw), Packages: []PackageRegistry{}, UniversalCompileValidityUnestablished: true}
	if runtime.Version() != input.Context.GoVersion {
		return out, fmt.Errorf("helper stdlib Go version differs from reviewed discovery source")
	}
	declarations := 0
	for _, pkg := range input.Packages {
		registry := discover(pkg)
		declarations += len(registry.Tests) + len(registry.Benchmarks) + len(registry.FuzzTargets) + len(registry.Examples) + len(registry.TestMains)
		if declarations > 10000 {
			return out, fmt.Errorf("declaration output count bound")
		}
		out.Packages = append(out.Packages, registry)
		if len(registry.Diagnostics) > 0 {
			out.State = "unresolved-source-discovery"
		}
	}
	return out, nil
}

func encodeOutput(out Output) ([]byte, error) {
	raw, err := json.Marshal(out)
	if err != nil {
		return nil, err
	}
	if len(raw) >= maxExpandedOutput {
		return nil, fmt.Errorf("expanded output bound")
	}
	// Canonical internal encoding: Go JSON sorted object keys, exact ordered
	// arrays, integer-preserving numbers, default Go JSON escaping, final LF.
	var ordered any
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	if err := decoder.Decode(&ordered); err != nil {
		return nil, err
	}
	raw, err = json.Marshal(ordered)
	if err != nil {
		return nil, err
	}
	raw = append(raw, '\n')
	if len(raw) > maxExpandedOutput {
		return nil, fmt.Errorf("expanded output bound")
	}
	var compressed bytes.Buffer
	writer, err := gzip.NewWriterLevel(&compressed, gzip.BestCompression)
	if err != nil {
		return nil, err
	}
	writer.Header.Name, writer.Header.Comment, writer.Header.Extra, writer.Header.OS = "", "", nil, 255
	// ModTime remains its zero value; no wall clock, filename or random header.
	if _, err := writer.Write(raw); err != nil {
		return nil, err
	}
	if err := writer.Close(); err != nil {
		return nil, err
	}
	if compressed.Len() > maxCompressedOutput {
		return nil, fmt.Errorf("compressed output bound")
	}
	return compressed.Bytes(), nil
}

func main() {
	raw, err := io.ReadAll(io.LimitReader(os.Stdin, maxInput+1))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	out, err := run(raw)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	wire, err := encodeOutput(out)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if written, err := os.Stdout.Write(wire); err != nil || written != len(wire) {
		fmt.Fprintln(os.Stderr, "output transport failed")
		os.Exit(2)
	}
	if out.State != "source-derived-uncompiled" {
		os.Exit(1)
	}
}
