from packaging import version

from webdriver_manager.core.driver import Driver
from webdriver_manager.core.logger import log
from webdriver_manager.core.utils import ChromeType, is_arch, is_mac_os
import re


class ChromeDriver(Driver):

    def __init__(
            self,
            name,
            version,
            os_type,
            url,
            latest_release_url,
            http_client,
            chrome_type=ChromeType.GOOGLE,
    ):
        super(ChromeDriver, self).__init__(
            name, version, os_type, url, latest_release_url, http_client
        )
        self._browser_type = chrome_type
        self._os_type = self.get_os_type()

    def get_os_type(self):
        os_type = super().get_os_type()
        if "win" in os_type:
            return "win32"

        if not is_mac_os(os_type):
            return os_type

        if is_arch(os_type):
            return "mac_arm64"

        return os_type

    def get_driver_download_url(self):
        driver_version_to_download = self.get_driver_version_to_download()
        os_type = self._os_type
        # For Mac ARM CPUs after version 106.0.5249.61 the format of OS type changed
        # to more unified "mac_arm64". For newer versions, it'll be "mac_arm64"
        # by default, for lower versions we replace "mac_arm64" to old format - "mac64_m1".
        if version.parse(driver_version_to_download) < version.parse("106.0.5249.61"):
            os_type = os_type.replace("mac_arm64", "mac64_m1")

        if version.parse(driver_version_to_download) >= version.parse("113"):
            if os_type == "mac64":
                os_type = "mac-x64"
            if os_type == "mac_x64":
                os_type = "mac-x64"
            if os_type in ["mac_64", "mac64_m1", "mac_arm64"]:
                os_type = "mac-arm64"
            modern_version_url = self.get_url_for_version_and_platform(driver_version_to_download, os_type)
            log(f"Modern chrome version {modern_version_url}")
            return modern_version_url
        return f"{self._url}/{driver_version_to_download}/{self.get_name()}_{os_type}.zip"

    def get_browser_type(self):
        return self._browser_type

    def get_latest_release_version(self):
        determined_browser_version = self.get_browser_version_from_os()

        log(f"Get LATEST {self._name} version for {self._browser_type}")
        if isinstance(determined_browser_version, str):
            if version.parse(determined_browser_version) >= version.parse("113"):
                return determined_browser_version

        latest_release_url = (
            self._latest_release_url
            if (self._version == "latest" or determined_browser_version is None)
            else f"{self._latest_release_url}_{determined_browser_version}"
        )
        resp = self._http_client.get(url=latest_release_url)
        return resp.text.rstrip()

    def select_url_from_versions(self, browser_version, versions, platform):
        for v in versions:
            if v["version"] == browser_version:
                downloads = v["downloads"]["chromedriver"]
                for d in downloads:
                    if d["platform"] == platform:
                        return d["url"]
        return None

    def get_url_for_version_and_platform(self, browser_version, platform):
        url = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
        response = self._http_client.get(url)
        data = response.json()
        versions = data["versions"]
        url = self.select_url_from_versions(browser_version, versions, platform)
        if url:
            return url
        elif len(browser_version) < 4:
            release_version = self.get_latest_release_for_version(browser_version)
            modern_version_url = self.select_url_from_versions(release_version, versions, platform)
            if modern_version_url != None:
                return modern_version_url
        elif re.search(r"^\d+\.\d+\.\d+$", browser_version):
            release_version = self.get_latest_patch_version_for_build_version(build_version=browser_version)
            modern_version_url = self.select_url_from_versions(release_version, versions, platform)
            if modern_version_url != None:
                return modern_version_url
        raise Exception(f"No such driver version {browser_version} for {platform}")

    def get_latest_release_for_version(self, version):
        url = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json"
        response = self._http_client.get(url)
        data = response.json()
        versions =[v["version"] for v in data["channels"].values()]
        for v in versions:
            if version in v:
                return v
        return None

    def get_latest_patch_version_for_build_version(self, build_version):
        url = "https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build.json"
        response = self._http_client.get(url)
        data = response.json()
        return data["builds"][build_version]["version"]
