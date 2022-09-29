def test_version():
    """Test version import."""
    from foliage import __version__
    assert __version__


def test_print_version(capsys):
    from foliage import print_version
    print_version()
    captured = capsys.readouterr()
    assert 'URL' in captured.out
