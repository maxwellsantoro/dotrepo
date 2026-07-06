# Contributing

## Running the test suite

We encourage you to check that the test suite passes locally before
submitting a pull request with your changes.

##### In the [`suite_core`] directory

```sh
# Test all the example code in the documentation
cargo check
```

##### In the [`test_suite`] directory

```sh
# Run the full test suite, including tests of unstable functionality
cargo +nightly test --features unstable
```

Note that this test suite currently only supports running on a nightly
compiler.
