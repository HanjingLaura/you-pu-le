from scripts.install_vercel import prune_example_scores


def test_package_pruning_preserves_modules_and_unrelated_files(tmp_path):
    corpus = tmp_path / "music21" / "corpus"
    corpus.mkdir(parents=True)
    module = corpus / "__init__.py"
    module.write_text("# Python module", encoding="utf-8")
    license_file = corpus / "license.txt"
    license_file.write_text("license", encoding="utf-8")
    data = corpus / "bach"
    data.mkdir()
    (data / "sample.musicxml").write_bytes(b"example")
    (data / "metadata.json.gz").write_bytes(b"compressed")
    outside = tmp_path / "uploaded.musicxml"
    outside.write_bytes(b"user score")

    assert prune_example_scores(corpus) == len(b"examplecompressed")
    assert module.is_file() and license_file.is_file()
    assert not list(data.iterdir())
    assert outside.read_bytes() == b"user score"
