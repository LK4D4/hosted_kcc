from hosted_kcc.cli import build_parser


def test_cli_defaults_to_kcc_base_image_c2e_executable():
    args = build_parser().parse_args([])

    assert args.kcc_command == "c2e"


def test_cli_defaults_config_to_data_volume():
    args = build_parser().parse_args([])

    assert args.config == "/data/config.toml"
