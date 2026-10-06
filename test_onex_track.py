#!/usr/bin/env python3

import copy
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import onex_track
from onex_track import (
    DIR_DICT,
    ONEX_INFO_URL,
    ONEX_PRETRACKING_URL,
    ONEX_TRACKING_URL,
    OnexStatus,
    fmt_estimated_date,
    get_at_wh_status,
    get_in_am_status,
    get_parcel_status,
    get_preonex_status,
    get_received_status,
    get_shipping_status,
    load_cache,
    notify,
    parse_args,
    process_package,
    reformat_date,
    save_cache,
    split_errors,
)


READY_FOR_PICKUP_DATA = {
    "import": {
        "country": "usa",
        "countryTo": "armenia",
        "trackingcode": "1Z0000000000000000",
        "weight": "4.300",
        "orderstatus": "in Armenia",
        "parcelid": "8820",
        "idbox": "86088",
        "dispatch": "0",
        "wo_scanneddate": "2020-01-01 10:00:00",
        "parcel_name": "DE 000",
        "p_inarmeniadateto": None,
        "p_inarmeniadate": "2020-01-10 12:00:00",
        "v_weight": "10.500",
        "inusadate": "2020-01-01 12:00:00",
        "inmywaydate": "2020-01-05 00:00:00",
        "inarmeniadate": "2020-01-10 15:00:00",
        "receiveddate": None,
        "estimateddate": "2020-01-10 12:00:00",
        "estimated_date_to": None,
        "estdateto": None,
    },
    "export": False,
    "track": {
        "id": 326323345,
        "tracking_number": "1Z0000000000000000",
        "tracking_number_secondary": None,
        "tracking_number_current": None,
        "courier": {
            "slug": "ups",
            "name": "UPS: United Parcel Service",
            "name_alt": None,
            "country_code": "USA",
            "review_count": 6,
            "review_score": "5.0000000000000000",
        },
        "is_active": False,
        "is_delivered": False,
        "last_check": "2020-01-01 18:00:00",
        "checkpoints": [],
        "extra": [],
    },
    "iherb": False,
    "warning_message": "",
    "tno": "1Z0000000000000000",
}


PREONEX_DATA = {
    "status": True,
    "data": {
        "id": 329497833,
        "tracking_number": "92000000000000000000000000",
        "tracking_number_secondary": None,
        "tracking_number_current": None,
        "courier": {
            "slug": "usps",
            "name": "Почта США",
            "name_alt": "USPS: The United States Postal Service",
            "country_code": "USA",
            "review_count": 12,
            "review_score": "4.3000000000000000"
        },
        "is_active": True,
        "is_delivered": False,
        "last_check": "2020-02-05 18:00:00",
        "checkpoints": [
            {
                "id": 4589466064,
                "time": "2020-02-05 12:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "in_delivery",
                "status_name": "Посылка выдана для доставки",
                "status_raw": "Out for Delivery",
                "location_translated": "Wilmington, DE",
                "location_raw": "Wilmington, DE",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4589466063,
                "time": "2020-02-05 10:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "arrived-destination",
                "status_name": "Прибыла в место назначения",
                "status_raw": "Arrived at Post Office",
                "location_translated": "Wilmington, DE",
                "location_raw": "Wilmington, DE",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4589288913,
                "time": "2020-02-04 18:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Прибыла в промежуточный пункт",
                "status_raw": "Arrived at USPS Regional Facility",
                "location_translated": "Wilmington, DE",
                "location_raw": "Wilmington, DE",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4589288912,
                "time": "2020-02-04 15:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Покинула промежуточный пункт",
                "status_raw": "Departed USPS Regional Facility",
                "location_translated": "Wilmington De Distribution Center",
                "location_raw": "Wilmington De Distribution Center",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4589288911,
                "time": "2020-02-04 12:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Покинула промежуточный пункт",
                "status_raw": "Departed USPS Regional Facility",
                "location_translated": "Wilmington De Distribution Center",
                "location_raw": "Wilmington De Distribution Center",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4589147870,
                "time": "2020-02-03 18:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Прибыла в промежуточный пункт",
                "status_raw": "Arrived at USPS Regional Facility",
                "location_translated": "Wilmington De Distribution Center",
                "location_raw": "Wilmington De Distribution Center",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4589026782,
                "time": "2020-02-03 12:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Покинула промежуточный пункт",
                "status_raw": "Departed USPS Regional Facility",
                "location_translated": "Warrendale Pa Distribution Center",
                "location_raw": "Warrendale Pa Distribution Center",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4588997866,
                "time": "2020-02-02 20:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Покинула промежуточный пункт",
                "status_raw": "Departed USPS Regional Facility",
                "location_translated": "Warrendale Pa Distribution Center",
                "location_raw": "Warrendale Pa Distribution Center",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4588973692,
                "time": "2020-02-02 18:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Прибыла в промежуточный пункт",
                "status_raw": "Arrived at USPS Regional Facility",
                "location_translated": "Warrendale Pa Distribution Center",
                "location_raw": "Warrendale Pa Distribution Center",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4588973691,
                "time": "2020-02-02 16:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Покинула промежуточный пункт",
                "status_raw": "Departed USPS Regional Facility",
                "location_translated": "",
                "location_raw": "",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4588949166,
                "time": "2020-02-02 12:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Покинула промежуточный пункт",
                "status_raw": "Departed USPS Regional Facility",
                "location_translated": "",
                "location_raw": "",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4588900508,
                "time": "2020-02-02 08:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Покинула промежуточный пункт",
                "status_raw": "Departed USPS Regional Facility",
                "location_translated": "",
                "location_raw": "",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4588797761,
                "time": "2020-02-01 22:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Покинула промежуточный пункт",
                "status_raw": "Departed USPS Regional Facility",
                "location_translated": "Saint Paul, MN",
                "location_raw": "Saint Paul, MN",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4588797760,
                "time": "2020-02-01 20:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Покинула промежуточный пункт",
                "status_raw": "Departed USPS Regional Facility",
                "location_translated": "Saint Paul, MN",
                "location_raw": "Saint Paul, MN",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4588797759,
                "time": "2020-02-01 18:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "transited",
                "status_name": "В пути - Покинула промежуточный пункт",
                "status_raw": "Departed USPS Regional Facility",
                "location_translated": "Saint Paul, MN",
                "location_raw": "Saint Paul, MN",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4588797758,
                "time": "2020-02-01 16:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "accepted",
                "status_name": "Посылка принята",
                "status_raw": "USPS in possession of item",
                "location_translated": "Saint Paul, MN",
                "location_raw": "Saint Paul, MN",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4588745964,
                "time": "2020-02-01 14:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "accepted",
                "status_name": "Посылка принята",
                "status_raw": "Accepted at USPS Origin Facility",
                "location_translated": "Saint Paul, MN",
                "location_raw": "Saint Paul, MN",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            },
            {
                "id": 4588745963,
                "time": "2020-02-01 12:00:00",
                "courier": {
                    "slug": "usps",
                    "name": "Почта США",
                    "name_alt": "USPS: The United States Postal Service",
                    "country_code": "USA",
                    "review_count": 12,
                    "review_score": "4.3000000000000000"
                },
                "status_code": "pre-registered",
                "status_name": "Информация о посылке получена",
                "status_raw": "Shipping Label Created, USPS Awaiting Item",
                "location_translated": "Saint Paul, MN",
                "location_raw": "Saint Paul, MN",
                "location_color_light": None,
                "location_color_dark": None,
                "location_zip_code": None
            }
        ],
        "extra": [
            {
                "courier_slug": "usps",
                "data": {
                    "weight.volume": None,
                    "weight.actual": None,
                    "weight.dimensions": None,
                    "weight.seats": None,
                    "recipient.title": None,
                    "recipient.location.title": None,
                    "recipient.location.zip_code": None,
                    "recipient.location.phone": None,
                    "sender.title": None,
                    "sender.location.title": None,
                    "sender.location.zip_code": None,
                    "service.name": "USPS Ground Advantage",
                    "shipment.order_number": None,
                    "shipment.delivery_date": None,
                    "shipment.pickup_ready_date": None,
                    "shipment.pickup_storage_date": None,
                    "shipment.value": None,
                    "shipment.cash_on_delivery": None,
                    "delivery.left_at": None,
                    "delivery.signed_by": None,
                    "alternative.tracking_number": None,
                    "internal_tracking": None
                }
            }
        ]
    },
    "message": "ok"
}


BASIC_INFO_PREONEX = {
    "import": None,
    "export": False,
    "track": copy.deepcopy(PREONEX_DATA["data"]),
    "iherb": False,
    "warning_message": "",
    "tno": PREONEX_DATA["data"]["tracking_number"],
}


def make_async_cm(response):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


class TestReadyForPickup(unittest.IsolatedAsyncioTestCase):
    """
    Tests for the 'ready for pickup' ('in Armenia') case using
    mocked input JSON data.
    """

    def setUp(self):
        self.ref_data = copy.deepcopy(READY_FOR_PICKUP_DATA)

    def test_mock_data_structure(self):
        """Ensure mock JSON structure matches expectations."""
        self.assertIn("import", self.ref_data)
        import_info = self.ref_data["import"]
        self.assertEqual(import_info["orderstatus"], "in Armenia")
        self.assertEqual(import_info["trackingcode"], "1Z0000000000000000")
        self.assertEqual(import_info["inarmeniadate"], "2020-01-10 15:00:00")
        self.assertEqual(self.ref_data["tno"], "1Z0000000000000000")

    async def test_get_in_am_status(self):
        """Test get_in_am_status directly with reference data."""
        mock_session = AsyncMock()
        msg_template, latest_entry = await get_in_am_status(self.ref_data, mock_session)

        self.assertEqual(
            msg_template,
            "Посылка «{label}» прибыла в Армению и готовится к доставке",
        )
        self.assertEqual(latest_entry["status"], OnexStatus.IN_ARMENIA.value)
        self.assertEqual(latest_entry["status"], "in Armenia")
        self.assertEqual(
            latest_entry["date"],
            self.ref_data["import"]["inarmeniadate"],
        )

    async def test_process_package_ready_for_pickup(self):
        """
        Test process_package with mocked API returning reference data
        for the 'ready for pickup' parcel.
        """
        mock_session = AsyncMock()
        tno = self.ref_data["tno"]
        label = "Order #123"

        with patch("onex_track._post_request", new_callable=AsyncMock) as mock_post:
            # _post_request returns {'data': ...}
            mock_post.return_value = {"data": copy.deepcopy(self.ref_data)}

            entry = await process_package(tno, label, mock_session)

            mock_post.assert_awaited_once_with(
                ONEX_INFO_URL,
                {"tcode": tno},
                mock_session,
            )

        self.assertEqual(entry["no"], tno)
        self.assertEqual(entry["label"], label)
        self.assertEqual(entry["status"], OnexStatus.IN_ARMENIA.value)
        self.assertEqual(entry["date"], "2020-01-10 15:00:00")

        # Estimated date should not be included for IN_ARMENIA status,
        # even though it is present in reference import data
        self.assertIn("estimateddate", self.ref_data["import"])
        self.assertNotIn("estimateddate", entry)
        self.assertNotIn("ожидается", entry["msg_template"])

        expected_msg_template = (
            "Посылка «{label}» прибыла в Армению и готовится к доставке\n"
            "(обновлено {date}, заказ № {no})"
        )
        self.assertEqual(entry["msg_template"], expected_msg_template)

        formatted_msg = entry["msg_template"].format(**entry)
        expected_msg = (
            f"Посылка «{label}» прибыла в Армению и готовится к доставке\n"
            f"(обновлено 2020-01-10 15:00:00, заказ № {tno})"
        )
        self.assertEqual(formatted_msg, expected_msg)

    async def test_process_package_ready_for_pickup_custom_label(self):
        """Test message formatting with unicode/custom labels."""
        mock_session = AsyncMock()
        tno = self.ref_data["tno"]
        label = "Тестовая посылка 📦"

        with patch("onex_track._post_request", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"data": copy.deepcopy(self.ref_data)}
            entry = await process_package(tno, label, mock_session)

        formatted_msg = entry["msg_template"].format(**entry)
        self.assertIn("Посылка «Тестовая посылка 📦» прибыла в Армению", formatted_msg)
        self.assertIn(f"заказ № {tno}", formatted_msg)

    def test_processor_dict_mapping(self):
        """Ensure processor dictionary maps IN_ARMENIA to get_in_am_status."""
        from onex_track import PROCESSOR_DICT
        self.assertIn(OnexStatus.IN_ARMENIA, PROCESSOR_DICT)
        self.assertIs(PROCESSOR_DICT[OnexStatus.IN_ARMENIA], get_in_am_status)
        # Verify lookup works by string key as well (from JSON)
        self.assertIs(PROCESSOR_DICT["in Armenia"], get_in_am_status)

    async def test_ready_for_pickup_caching_behavior(self):
        """Verify caching behavior for ready for pickup status."""
        mock_session = MagicMock()
        cache_url = "https://api.jsonbin.io/v3/b/dummy/latest?meta=false"

        initial_cache = {}
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json = AsyncMock(return_value=initial_cache)
        mock_session.get.return_value = make_async_cm(mock_response)

        cache_data, is_cached = await load_cache(cache_url, mock_session)

        entry = {
            "no": self.ref_data["tno"],
            "status": OnexStatus.IN_ARMENIA.value,
            "date": self.ref_data["import"]["inarmeniadate"],
        }

        # First time seen: not cached, should be added to cache_data
        self.assertFalse(is_cached(entry))
        self.assertEqual(cache_data[entry["no"]], [entry["status"], entry["date"]])

        # Second time seen: already cached
        self.assertTrue(is_cached(entry))


class TestPreOnex(unittest.IsolatedAsyncioTestCase):
    """
    Tests for the pre-Onex status using mocked input JSON data from preonex.json.
    """

    def setUp(self):
        self.preonex_data = copy.deepcopy(PREONEX_DATA)
        self.basic_info = copy.deepcopy(BASIC_INFO_PREONEX)

    def test_mock_data_structure(self):
        """Ensure mock JSON structure matches expectations."""
        self.assertTrue(self.preonex_data["status"])
        data = self.preonex_data["data"]
        self.assertEqual(data["tracking_number"], "92000000000000000000000000")
        self.assertEqual(data["courier"]["slug"], "usps")
        self.assertEqual(data["courier"]["name"], "Почта США")
        self.assertGreater(len(data["checkpoints"]), 0)

        latest_cp = data["checkpoints"][0]
        self.assertEqual(latest_cp["location_translated"], "Wilmington, DE")
        self.assertEqual(latest_cp["status_name"], "Посылка выдана для доставки")
        self.assertEqual(latest_cp["time"], "2020-02-05 12:00:00")

    async def test_get_preonex_status(self):
        """Test get_preonex_status directly with reference preonex data."""
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.read = AsyncMock(
            return_value=json.dumps(self.preonex_data).encode("utf-8")
        )
        mock_session.post.return_value = make_async_cm(mock_resp)

        msg_template, latest_entry = await get_preonex_status(
            self.basic_info, mock_session
        )

        mock_session.post.assert_called_once_with(
            ONEX_PRETRACKING_URL,
            params={"track": self.basic_info["tno"]},
            headers=onex_track.ONEX_HEADERS,
        )
        self.assertEqual(msg_template, "{label}: {status} ({place})")
        self.assertEqual(latest_entry["place"], "Wilmington, DE")
        self.assertEqual(latest_entry["status"], "посылка выдана для доставки")
        self.assertEqual(latest_entry["date"], "2020-02-05 12:00:00")

    async def test_get_preonex_status_no_checkpoints(self):
        """Test get_preonex_status when courier hasn't reported checkpoints yet."""
        mock_session = MagicMock()
        empty_checkpoints_data = copy.deepcopy(self.preonex_data)
        empty_checkpoints_data["data"]["checkpoints"] = []
        mock_resp = MagicMock()
        mock_resp.read = AsyncMock(
            return_value=json.dumps(empty_checkpoints_data).encode("utf-8")
        )
        mock_session.post.return_value = make_async_cm(mock_resp)

        msg_template, latest_entry = await get_preonex_status(
            self.basic_info, mock_session
        )

        self.assertEqual(
            msg_template,
            "{courier} пока не предоставил(а) информацию о посылке {label}",
        )
        self.assertEqual(latest_entry["courier"], "Почта США")
        self.assertEqual(latest_entry["date"], "2020-02-05 18:00:00")

    async def test_get_preonex_status_no_data_raises_value_error(self):
        """Ensure get_preonex_status raises ValueError when response has no data."""
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.read = AsyncMock(
            return_value=json.dumps({"status": True, "data": None}).encode("utf-8")
        )
        mock_session.post.return_value = make_async_cm(mock_resp)

        with self.assertRaises(ValueError) as ctx:
            await get_preonex_status(self.basic_info, mock_session)
        self.assertIn("No data collected for", str(ctx.exception))

    async def test_process_package_preonex(self):
        """
        Test process_package with mocked API returning preonex data
        before package arrives at Onex warehouse.
        """
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.read = AsyncMock(
            return_value=json.dumps(self.preonex_data).encode("utf-8")
        )
        mock_session.post.return_value = make_async_cm(mock_resp)

        tno = self.basic_info["tno"]
        label = "Order #456"

        with patch("onex_track._post_request", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"data": copy.deepcopy(self.basic_info)}

            entry = await process_package(tno, label, mock_session)

            mock_post.assert_awaited_once_with(
                ONEX_INFO_URL,
                {"tcode": tno},
                mock_session,
            )

        self.assertEqual(entry["no"], tno)
        self.assertEqual(entry["label"], label)
        self.assertEqual(entry["place"], "Wilmington, DE")
        self.assertEqual(entry["status"], "посылка выдана для доставки")
        self.assertEqual(entry["date"], "2020-02-05 12:00:00")
        self.assertNotIn("estimateddate", entry)

        expected_msg_template = (
            "{label}: {status} ({place})\n"
            "(обновлено {date}, заказ № {no})"
        )
        self.assertEqual(entry["msg_template"], expected_msg_template)

        formatted_msg = entry["msg_template"].format(**entry)
        expected_msg = (
            f"{label}: посылка выдана для доставки (Wilmington, DE)\n"
            f"(обновлено 2020-02-05 12:00:00, заказ № {tno})"
        )
        self.assertEqual(formatted_msg, expected_msg)

    async def test_process_package_preonex_custom_label(self):
        """Test message formatting with unicode/custom labels for pre-Onex."""
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.read = AsyncMock(
            return_value=json.dumps(self.preonex_data).encode("utf-8")
        )
        mock_session.post.return_value = make_async_cm(mock_resp)

        tno = self.basic_info["tno"]
        label = "Тестовый заказ 📦"

        with patch("onex_track._post_request", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"data": copy.deepcopy(self.basic_info)}
            entry = await process_package(tno, label, mock_session)

        formatted_msg = entry["msg_template"].format(**entry)
        self.assertIn("Тестовый заказ 📦: посылка выдана для доставки (Wilmington, DE)", formatted_msg)
        self.assertIn(f"заказ № {tno}", formatted_msg)

    async def test_preonex_caching_behavior(self):
        """Verify caching behavior for pre-Onex status."""
        mock_session = MagicMock()
        cache_url = "https://api.jsonbin.io/v3/b/dummy/latest?meta=false"

        initial_cache = {}
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json = AsyncMock(return_value=initial_cache)
        mock_session.get.return_value = make_async_cm(mock_response)

        cache_data, is_cached = await load_cache(cache_url, mock_session)

        latest_cp = self.preonex_data["data"]["checkpoints"][0]
        entry = {
            "no": self.basic_info["tno"],
            "status": latest_cp["status_name"].lower(),
            "date": latest_cp["time"],
        }

        # First time seen: not cached, should be added to cache_data
        self.assertFalse(is_cached(entry))
        self.assertEqual(cache_data[entry["no"]], [entry["status"], entry["date"]])

        # Second time seen: already cached
        self.assertTrue(is_cached(entry))


class TestDateFormatting(unittest.TestCase):
    """Tests for date formatting helpers in onex_track."""

    def test_reformat_date(self):
        dt_str = "2020-01-10 12:00:00"
        single_res = reformat_date(dt_str, single=True)
        range_res = reformat_date(dt_str, single=False)
        self.assertIsInstance(single_res, str)
        self.assertIsInstance(range_res, str)
        self.assertTrue(len(single_res) > 0)
        self.assertTrue(len(range_res) > 0)

    def test_fmt_estimated_date_single(self):
        import_data = {
            "estimateddate": "2020-01-10 12:00:00",
            "estimated_date_to": None,
        }
        res = fmt_estimated_date(import_data)
        self.assertTrue(res.startswith("в "))

    def test_fmt_estimated_date_range(self):
        import_data = {
            "estimateddate": "2020-01-10 12:00:00",
            "estimated_date_to": "2020-01-15 12:00:00",
        }
        res = fmt_estimated_date(import_data)
        self.assertIn("–", res)


class TestOtherStatuses(unittest.IsolatedAsyncioTestCase):
    """Tests for warehouse, transit, received, and pre-onex statuses."""

    async def test_get_at_wh_status(self):
        mock_session = AsyncMock()
        data = {"import": {"inusadate": "2020-01-01 10:00:00"}}
        msg_template, entry = await get_at_wh_status(data, mock_session)
        self.assertEqual(msg_template, "Посылка «{label}» доставлена на склад Onex")
        self.assertEqual(entry["status"], "at_wh")
        self.assertEqual(entry["date"], "2020-01-01 10:00:00")

    async def test_get_received_status(self):
        mock_session = AsyncMock()
        data = {"import": {"receiveddate": "2020-01-20 12:00:00"}}
        msg_template, entry = await get_received_status(data, mock_session)
        self.assertEqual(msg_template, "Посылка «{label}» доставлена и получена")
        self.assertEqual(entry["status"], OnexStatus.RECEIVED.value)
        self.assertEqual(entry["date"], "2020-01-20 12:00:00")

    async def test_get_shipping_status(self):
        mock_session = AsyncMock()
        data = {
            "tno": "T123",
            "import": {
                "parcelid": "111",
                "idbox": "222",
                "inmywaydate": "2020-01-05 00:00:00",
            },
        }
        tracking_info = [
            {"hub": "Аэропорт", "type": "out", "date": "2020-01-06 12:00:00"}
        ]
        with patch("onex_track._post_request", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"data": tracking_info}
            msg_tmpl, entry = await get_shipping_status(data, mock_session)

            mock_post.assert_awaited_once_with(
                ONEX_TRACKING_URL,
                {"parcel_id": "111", "idbox": "222"},
                mock_session,
            )

        self.assertEqual(msg_tmpl, "Посылка «{label}» {dir} {hub}")
        self.assertEqual(entry["hub"], "Аэропорт")
        self.assertEqual(entry["type"], "out")
        self.assertEqual(entry["dir"], DIR_DICT["out"])
        self.assertEqual(entry["status"], "moving")

    async def test_get_preonex_status_no_checkpoints(self):
        mock_session = MagicMock()
        data = {
            "tno": "T999",
            "track": {
                "courier": {"name": "FedEx"},
                "last_check": "2020-01-01 10:00:00",
            },
        }
        mock_resp = MagicMock()
        mock_resp.read = AsyncMock(
            return_value=json.dumps({"data": {"checkpoints": []}}).encode("utf-8")
        )
        mock_session.post.return_value = make_async_cm(mock_resp)

        msg_tmpl, entry = await get_preonex_status(data, mock_session)
        self.assertIn("FedEx", msg_tmpl.format(courier="FedEx", label="pkg"))
        self.assertEqual(entry["courier"], "FedEx")
        self.assertEqual(entry["date"], "2020-01-01 10:00:00")

    async def test_get_preonex_status_with_checkpoints(self):
        mock_session = MagicMock()
        data = {
            "tno": "T999",
            "track": {
                "courier": {"name": "FedEx"},
                "last_check": "2020-01-01 10:00:00",
            },
        }
        checkpoints = [
            {
                "location_translated": "New York",
                "status_name": "In Transit",
                "time": "2020-01-02 12:00:00",
            }
        ]
        mock_resp = MagicMock()
        mock_resp.read = AsyncMock(
            return_value=json.dumps({"data": {"checkpoints": checkpoints}}).encode("utf-8")
        )
        mock_session.post.return_value = make_async_cm(mock_resp)

        msg_tmpl, entry = await get_preonex_status(data, mock_session)
        self.assertEqual(entry["place"], "New York")
        self.assertEqual(entry["status"], "in transit")
        self.assertEqual(entry["date"], "2020-01-02 12:00:00")


class TestUtilities(unittest.IsolatedAsyncioTestCase):
    """Tests for cache, notify, error splitting, and args."""

    def test_split_errors(self):
        val = {"status": "ok"}
        err = ValueError("Something failed")
        results, errors = split_errors([val, err])
        self.assertEqual(results, [val])
        self.assertEqual(errors, [err])

    async def test_notify(self):
        mock_session = MagicMock()
        mock_session.post = AsyncMock()
        await notify("my-topic", "Title", "Body message", mock_session)
        mock_session.post.assert_awaited_once_with(
            "https://ntfy.sh/my-topic",
            headers={"Title": "Title", "Tag": "package"},
            data="Body message",
        )

    async def test_save_cache(self):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_session.put.return_value = make_async_cm(mock_resp)

        data = {"b": ["status", "2020-01-02"], "a": ["status", "2020-01-01"]}
        await save_cache("https://api.jsonbin.io/v3/b/123", data, mock_session)
        mock_session.put.assert_called_once()

    def test_parse_args(self):
        with patch(
            "sys.argv",
            ["onex_track.py", "-t", "T1:Label1", "-n", "-c"],
        ):
            args = parse_args()
            self.assertEqual(args.track, ["T1:Label1"])
            self.assertTrue(args.no_notification)
            self.assertTrue(args.no_cache)

    @patch("onex_track.save_cache", new_callable=AsyncMock)
    @patch("onex_track.notify", new_callable=AsyncMock)
    @patch("onex_track.process_package", new_callable=AsyncMock)
    @patch("onex_track.load_cache", new_callable=AsyncMock)
    @patch("onex_track._check_connection", new_callable=AsyncMock)
    @patch("onex_track.aiohttp.ClientSession")
    async def test_main_saves_cache_after_successful_notification(
        self, mock_session_cls, mock_conn, mock_load, mock_proc, mock_notify, mock_save
    ):
        mock_session = AsyncMock()
        mock_session_cls.return_value = mock_session
        cache_data = {}
        mock_load.return_value = (cache_data, lambda entry: False)
        mock_proc.return_value = {
            "no": "T1",
            "label": "Label1",
            "status": "in transit",
            "date": "2020-01-01",
            "msg_template": "{label}: {status}",
        }

        with patch(
            "sys.argv",
            ["onex_track.py", "-t", "T1:Label1", "-T", "test-topic", "-b", "bin123"],
        ):
            await onex_track.main()

        mock_notify.assert_awaited_once()
        mock_save.assert_awaited_once()

    @patch("onex_track.save_cache", new_callable=AsyncMock)
    @patch("onex_track.notify", new_callable=AsyncMock)
    @patch("onex_track.process_package", new_callable=AsyncMock)
    @patch("onex_track.load_cache", new_callable=AsyncMock)
    @patch("onex_track._check_connection", new_callable=AsyncMock)
    @patch("onex_track.aiohttp.ClientSession")
    async def test_main_does_not_save_cache_if_notification_fails(
        self, mock_session_cls, mock_conn, mock_load, mock_proc, mock_notify, mock_save
    ):
        mock_session = AsyncMock()
        mock_session_cls.return_value = mock_session
        cache_data = {}
        mock_load.return_value = (cache_data, lambda entry: False)
        mock_proc.return_value = {
            "no": "T1",
            "label": "Label1",
            "status": "in transit",
            "date": "2020-01-01",
            "msg_template": "{label}: {status}",
        }
        mock_notify.side_effect = RuntimeError("Notification failed")

        with patch(
            "sys.argv",
            ["onex_track.py", "-t", "T1:Label1", "-T", "test-topic", "-b", "bin123"],
        ):
            with self.assertRaises(ExceptionGroup):
                await onex_track.main()

        mock_notify.assert_awaited_once()
        mock_save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
