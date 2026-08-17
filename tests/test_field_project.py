import json
import os
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from scripts.configure_field_project import (
    PHOTO_EXPRESSION,
    configure_project_xml,
    configure_qgz,
)


def _layer(name, layer_id, fields):
    layer = ET.Element("maplayer", {"type": "vector", "readOnly": "0"})
    ET.SubElement(layer, "id").text = layer_id
    ET.SubElement(layer, "layername").text = name
    configuration = ET.SubElement(layer, "fieldConfiguration")
    constraints = ET.SubElement(layer, "constraints")
    custom = ET.SubElement(layer, "customproperties")
    ET.SubElement(custom, "Option", {"type": "Map"})
    ET.SubElement(layer, "datasource").text = f"./{name}.gpkg|layername={name}"
    ET.SubElement(layer, "provider").text = "ogr"
    for field_name in fields:
        field = ET.SubElement(configuration, "field", {"name": field_name})
        widget = ET.SubElement(field, "editWidget", {"type": "TextEdit"})
        config = ET.SubElement(widget, "config")
        ET.SubElement(config, "Option", {"type": "Map"})
        ET.SubElement(
            constraints,
            "constraint",
            {
                "field": field_name,
                "constraints": "0",
                "notnull_strength": "0",
                "unique_strength": "0",
                "exp_strength": "0",
            },
        )
    return layer


def _project_xml():
    root = ET.Element("qgis")
    tree = ET.SubElement(root, "layer-tree-group")
    layers = ET.SubElement(root, "projectlayers")
    photos = _layer("photos", "photos_id", ["photo", "external_pk"])
    external = next(
        field for field in photos.findall("./fieldConfiguration/field")
        if field.get("name") == "external_pk"
    )
    external.find("editWidget").set("type", "RelationReference")
    option_map = external.find("./editWidget/config/Option")
    ET.SubElement(
        option_map,
        "Option",
        {"name": "AllowNULL", "type": "bool", "value": "true"},
    )
    ET.SubElement(
        option_map,
        "Option",
        {
            "name": "ReferencedLayerDataSource",
            "type": "QString",
            "value": "/private/old/Инцидент.gpkg|layername=Инцидент",
        },
    )
    layers.append(photos)
    incident = _layer(
        "Инцидент",
        "incident_id",
        ["incident_type", "volunteer_email", "unique-id"],
    )
    layers.append(incident)
    reference = _layer("ООПТ", "protected_id", ["name"])
    reference.find("datasource").text = (
        "/Users/example/source/Национальный_Парк.gpkg|layername=merged"
    )
    layers.append(reference)
    for layer in (photos, incident, reference):
        ET.SubElement(
            tree,
            "layer-tree-layer",
            {
                "id": layer.findtext("id"),
                "name": layer.findtext("layername"),
                "source": layer.findtext("datasource"),
                "checked": "Qt::Unchecked",
            },
        )
    ET.SubElement(
        root,
        "ProjectGpsSettings",
        {
            "destinationLayer": "protected_id",
            "destinationLayerSource": "/Users/example/Национальный_Парк.gpkg",
            "destinationLayerName": "ООПТ",
            "destinationFollowsActiveLayer": "1",
        },
    )
    properties = ET.SubElement(root, "properties")
    qfield_sync = ET.SubElement(properties, "QFieldSync")
    ET.SubElement(qfield_sync, "exportDirectoryProject").text = "/private/export"
    return ET.tostring(root, encoding="utf-8")


def _write_incident_database(path, rows=()):
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            'CREATE TABLE "Инцидент" '
            '(fid INTEGER PRIMARY KEY, geom BLOB, "unique-id" TEXT)'
        )
        connection.execute(
            'CREATE TRIGGER incident_generic_update AFTER UPDATE ON "Инцидент" '
            'WHEN OLD.fid != NEW.fid AND ST_IsEmpty(NEW.geom) '
            'BEGIN SELECT ST_MinX(NEW.geom), ST_MaxX(NEW.geom), '
            'ST_MinY(NEW.geom), ST_MaxY(NEW.geom); END'
        )
        connection.executemany(
            'INSERT INTO "Инцидент" (fid, "unique-id") VALUES (?, ?)',
            rows,
        )
        connection.commit()
    finally:
        connection.close()


class FieldProjectTests(unittest.TestCase):
    def test_configures_required_fields_and_attachment_naming(self):
        root = ET.fromstring(configure_project_xml(_project_xml()))
        photos = next(
            layer for layer in root.findall(".//maplayer")
            if layer.findtext("layername") == "photos"
        )
        incidents = next(
            layer for layer in root.findall(".//maplayer")
            if layer.findtext("layername") == "Инцидент"
        )

        for layer, field_name in (
            (photos, "photo"),
            (photos, "external_pk"),
            (incidents, "incident_type"),
            (incidents, "volunteer_email"),
        ):
            constraint = next(
                item for item in layer.findall("./constraints/constraint")
                if item.get("field") == field_name
            )
            self.assertEqual("1", constraint.get("constraints"))
            self.assertEqual("1", constraint.get("notnull_strength"))

        options = {
            item.get("name"): item.get("value")
            for item in photos.findall("./customproperties/Option/Option")
        }
        self.assertEqual(
            {"photo": PHOTO_EXPRESSION},
            json.loads(options["QFieldSync/attachment_naming"]),
        )
        self.assertEqual(
            PHOTO_EXPRESSION,
            root.findtext("./properties/Mergin/PhotoNaming/photos_id/photo"),
        )

        layers_by_name = {
            layer.findtext("layername"): layer
            for layer in root.findall(".//maplayer")
        }
        self.assertEqual("0", layers_by_name["photos"].get("readOnly"))
        self.assertEqual("0", layers_by_name["Инцидент"].get("readOnly"))
        self.assertEqual("1", layers_by_name["ООПТ"].get("readOnly"))
        self.assertEqual(
            "./Национальный_Парк.gpkg|layername=merged",
            layers_by_name["ООПТ"].findtext("datasource"),
        )
        reference_tree = next(
            item for item in root.findall(".//layer-tree-layer")
            if item.get("id") == "protected_id"
        )
        self.assertEqual(
            "./Национальный_Парк.gpkg|layername=merged",
            reference_tree.get("source"),
        )
        incident_tree = next(
            item for item in root.findall(".//layer-tree-layer")
            if item.get("id") == "incident_id"
        )
        self.assertEqual("Qt::Checked", incident_tree.get("checked"))
        gps = root.find("ProjectGpsSettings")
        self.assertEqual("incident_id", gps.get("destinationLayer"))
        self.assertEqual("Инцидент", gps.get("destinationLayerName"))
        self.assertEqual("0", gps.get("destinationFollowsActiveLayer"))
        self.assertEqual(
            "./Инцидент.gpkg|layername=Инцидент",
            gps.get("destinationLayerSource"),
        )
        self.assertIsNone(
            root.find("./properties/QFieldSync/exportDirectoryProject").text
        )
        unique_constraint = next(
            item for item in layers_by_name["Инцидент"].findall(
                "./constraints/constraint"
            )
            if item.get("field") == "unique-id"
        )
        self.assertEqual("3", unique_constraint.get("constraints"))
        self.assertEqual("1", unique_constraint.get("notnull_strength"))
        self.assertEqual("1", unique_constraint.get("unique_strength"))
        unique_default = next(
            item for item in layers_by_name["Инцидент"].findall(
                "./defaults/default"
            )
            if item.get("field") == "unique-id"
        )
        self.assertEqual("uuid()", unique_default.get("expression"))

    def test_qgz_copies_nested_geopackage_to_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            os.mkdir(os.path.join(directory, "nested"))
            nested = os.path.join(directory, "nested", "ООПТ.gpkg")
            with open(nested, "wb") as stream:
                stream.write(b"test-geopackage")

            root = ET.fromstring(_project_xml())
            reference = next(
                layer for layer in root.findall(".//maplayer")
                if layer.findtext("layername") == "ООПТ"
            )
            reference.find("datasource").text = "./nested/ООПТ.gpkg|layername=merged"
            qgz = os.path.join(directory, "alma_bot.qgz")
            with zipfile.ZipFile(qgz, "w") as archive:
                archive.writestr("alma_bot.qgs", ET.tostring(root, encoding="utf-8"))

            with open(os.path.join(directory, "photos.gpkg"), "wb") as stream:
                stream.write(b"photos")
            _write_incident_database(os.path.join(directory, "Инцидент.gpkg"))

            configure_qgz(qgz)

            self.assertTrue(os.path.isfile(os.path.join(directory, "ООПТ.gpkg")))
            with zipfile.ZipFile(qgz) as archive:
                configured = ET.fromstring(archive.read("alma_bot.qgs"))
            reference = next(
                layer for layer in configured.findall(".//maplayer")
                if layer.findtext("layername") == "ООПТ"
            )
            self.assertEqual(
                "./ООПТ.gpkg|layername=merged",
                reference.findtext("datasource"),
            )

    def test_qgz_rejects_missing_geopackage(self):
        with tempfile.TemporaryDirectory() as directory:
            qgz = os.path.join(directory, "alma_bot.qgz")
            with zipfile.ZipFile(qgz, "w") as archive:
                archive.writestr("alma_bot.qgs", _project_xml())
            with self.assertRaisesRegex(ValueError, "Missing GeoPackage"):
                configure_qgz(qgz)

    def test_qgz_does_not_overwrite_different_root_geopackage(self):
        with tempfile.TemporaryDirectory() as directory:
            os.mkdir(os.path.join(directory, "nested"))
            with open(os.path.join(directory, "nested", "ООПТ.gpkg"), "wb") as stream:
                stream.write(b"reviewed-source")
            with open(os.path.join(directory, "ООПТ.gpkg"), "wb") as stream:
                stream.write(b"different-root-data")
            with open(os.path.join(directory, "photos.gpkg"), "wb") as stream:
                stream.write(b"photos")
            _write_incident_database(os.path.join(directory, "Инцидент.gpkg"))

            root = ET.fromstring(_project_xml())
            reference = next(
                layer for layer in root.findall(".//maplayer")
                if layer.findtext("layername") == "ООПТ"
            )
            reference.find("datasource").text = "./nested/ООПТ.gpkg|layername=merged"
            qgz = os.path.join(directory, "alma_bot.qgz")
            with zipfile.ZipFile(qgz, "w") as archive:
                archive.writestr("alma_bot.qgs", ET.tostring(root, encoding="utf-8"))

            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                configure_qgz(qgz)

    def test_qgz_backfills_blank_incident_relation_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            qgz = os.path.join(directory, "alma_bot.qgz")
            with zipfile.ZipFile(qgz, "w") as archive:
                archive.writestr("alma_bot.qgs", _project_xml())
            with open(os.path.join(directory, "photos.gpkg"), "wb") as stream:
                stream.write(b"photos")
            with open(os.path.join(directory, "Национальный_Парк.gpkg"), "wb") as stream:
                stream.write(b"reference")
            incident_path = os.path.join(directory, "Инцидент.gpkg")
            _write_incident_database(
                incident_path,
                [(1, None), (2, ""), (3, "{existing-id}")],
            )

            configure_qgz(qgz)

            connection = sqlite3.connect(incident_path)
            try:
                values = connection.execute(
                    'SELECT "unique-id" FROM "Инцидент" ORDER BY fid'
                ).fetchall()
            finally:
                connection.close()
            self.assertEqual("{existing-id}", values[2][0])
            self.assertEqual(3, len({value[0] for value in values}))
            self.assertTrue(all(value[0].startswith("{") for value in values))

    def test_qgz_rejects_duplicate_existing_incident_relation_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            qgz = os.path.join(directory, "alma_bot.qgz")
            with zipfile.ZipFile(qgz, "w") as archive:
                archive.writestr("alma_bot.qgs", _project_xml())
            with open(os.path.join(directory, "photos.gpkg"), "wb") as stream:
                stream.write(b"photos")
            with open(os.path.join(directory, "Национальный_Парк.gpkg"), "wb") as stream:
                stream.write(b"reference")
            _write_incident_database(
                os.path.join(directory, "Инцидент.gpkg"),
                [(1, "{duplicate}"), (2, "{duplicate}")],
            )

            with self.assertRaisesRegex(ValueError, "duplicate unique-id"):
                configure_qgz(qgz)

    def test_rejects_project_without_expected_layer(self):
        root = ET.fromstring(_project_xml())
        layers = root.find("projectlayers")
        for layer in list(layers):
            if layer.findtext("layername") == "photos":
                layers.remove(layer)
        with self.assertRaisesRegex(ValueError, "photos"):
            configure_project_xml(ET.tostring(root, encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
