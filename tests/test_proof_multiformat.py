from __future__ import annotations

import zipfile

from PIL import Image

from reprofig import attach_evidence_graph, build_record
from reprofig.artifacts import embed_file, extract_record, validate_artifact
from reprofig.crypto.encryption import decrypt_sections, encrypt_sections
from reprofig.crypto.keys import generate_signing_key
from reprofig.crypto.signatures import sign_record, verify_record_signatures


def _source(path, format_name):
    if format_name == "svg":
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>')
    elif format_name in {"png", "jpeg", "tiff", "webp", "avif"}:
        save_format = {"jpeg": "JPEG", "tiff": "TIFF"}.get(format_name, format_name.upper())
        Image.new("RGB", (8, 6), "green").save(path, format=save_format)
    elif format_name == "heif":
        import pillow_heif

        pillow_heif.from_pillow(Image.new("RGB", (8, 6), "green")).save(path)
    elif format_name == "pdf":
        import pikepdf

        with pikepdf.Pdf.new() as document:
            document.add_blank_page(page_size=(100, 100))
            document.save(path)
    elif format_name in {"pptx", "docx", "xlsx"}:
        marker = {
            "pptx": "ppt/presentation.xml",
            "docx": "word/document.xml",
            "xlsx": "xl/workbook.xml",
        }[format_name]
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(marker, "<root/>")
            archive.writestr(
                "[Content_Types].xml",
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
            )
    elif format_name == "html":
        path.write_text("<!doctype html><html><body>figure</body></html>")
    elif format_name == "hdf5":
        import h5py

        with h5py.File(path, "w") as file:
            file.create_dataset("values", data=[1, 2, 3])
    elif format_name == "netcdf":
        import netCDF4

        with netCDF4.Dataset(path, "w", format="NETCDF4") as dataset:
            dataset.createDimension("x", 3)
            dataset.createVariable("values", "i4", ("x",))[:] = [1, 2, 3]
    elif format_name == "fits":
        from astropy.io import fits

        fits.PrimaryHDU(data=[[1, 2], [3, 4]]).writeto(path)
    elif format_name == "zip":
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("README.txt", "proof fixture")
    else:  # pragma: no cover - the explicit matrix below is the contract
        raise AssertionError(format_name)


def test_signed_encrypted_record_round_trips_through_all_sixteen_carriers(tmp_path):
    extensions = {
        "svg": ".svg", "pdf": ".pdf", "png": ".png", "jpeg": ".jpg",
        "tiff": ".tif", "webp": ".webp", "avif": ".avif", "heif": ".heif",
        "pptx": ".pptx", "docx": ".docx", "xlsx": ".xlsx", "html": ".html",
        "netcdf": ".nc", "hdf5": ".h5", "fits": ".fits", "zip": ".zip",
    }
    master = attach_evidence_graph(build_record(
        plotted_data=[{"subject": "A", "value": 1.25}],
        statistics=[{"test_id": "summary", "n": 1}],
    ))
    table_id = f"table:{master.data_tables[0].sha256}"
    protected = encrypt_sections(master, [table_id], password="carrier password")
    key = tmp_path / "signing.pem"
    generate_signing_key(key, password="signing password")
    signed = sign_record(
        protected, private_key_path=str(key), password="signing password"
    )
    expected_root = signed.extensions["proof"]["root_sha256"]

    for format_name, suffix in extensions.items():
        source = tmp_path / f"source-{format_name}{suffix}"
        target = tmp_path / f"proof-{format_name}{suffix}"
        _source(source, format_name)
        embed_file(
            source,
            signed,
            output_path=target,
            allow_reencode=format_name in {"avif", "heif"},
        )
        assert validate_artifact(target).valid, format_name
        recovered = extract_record(target)
        assert recovered.extensions["proof"]["root_sha256"] == expected_root
        assert all(
            check.status == "pass" for check in verify_record_signatures(recovered)
        ), format_name
        decrypted = decrypt_sections(recovered, password="carrier password")
        assert "subject" in str(decrypted[table_id]), format_name
