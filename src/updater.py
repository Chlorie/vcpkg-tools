import os
import shutil
import hashlib
import json
import subprocess as sp
import requests
from typing import List, Optional, cast
from git import Repo

from .config import Config
from .logging import info, error
from .portfile import Portfile
from .manifest import Manifest


class Updater:
    def __init__(self, config: Config):
        self._config = config
        self._proxy = {
            'http': os.environ.get("http_proxy"),
            'https': os.environ.get("https_proxy")
        }
        self._portfile: Optional[Portfile] = None
        self._manifest: Optional[Manifest] = None
        self._latest_ref: str = ""
        self._vcpkg_latest_ref: str = ""
        self._repo = Repo(self._config.ports_path)

    def run(self):
        self._print_config()
        self._get_portfile()
        portfile = cast(Portfile, self._portfile)
        self._latest_ref = self._get_latest_ref(portfile.repo, portfile.head_ref)
        self._vcpkg_latest_ref = self._get_latest_ref("microsoft/vcpkg", "master")
        self._get_manifest()
        self._update_port()
        self._update_versions()
        self._setup_test()
        self._test_install()
        self._push_remote()
        info("Port {} updated successfully!", self._config.name)

    def _print_config(self):
        info("Config:")
        info("    Port name:         {}", self._config.name)
        info("    Ports path:        {}", self._config.ports_path)
        info("    Push to remote:    {}", self._config.push)
        info("    Fix failed update: {}", self._config.fix)

    def _get_portfile(self):
        info("Parsing portfile.cmake...")
        path = self._config.ports_path / "ports" / self._config.name / "portfile.cmake"
        self._portfile = Portfile(path)
        info("Current portfile paramaters:")
        info("    REPO:     {}", self._portfile.repo)
        info("    REF:      {}", self._portfile.ref)
        info("    SHA512:   {}", self._portfile.sha512)
        info("    HEAD_REF: {}", self._portfile.head_ref)

    def _get_latest_ref(self, repo: str, head_ref: str) -> str:
        info(f"Retrieving latest ref from {repo}:{head_ref}...")
        uri = f"https://api.github.com/repos/{repo}/commits/{head_ref}"
        res = requests.get(uri, proxies=self._proxy)
        if res.status_code != 200:
            error("Failed to retrieve latest ref, status code {}", res.status_code)
        sha = res.json()['sha']
        info("Latest commit reference: {}", sha)
        return sha

    def _get_manifest(self):
        info("Fetching manifest...")
        portfile = cast(Portfile, self._portfile)
        uri = f"https://raw.githubusercontent.com/{portfile.repo}/{self._latest_ref}/vcpkg.json"
        res = requests.get(uri, proxies=self._proxy)
        if res.status_code != 200:
            error("Failed to fetch manifest, status code {}", res.status_code)
        self._manifest = Manifest(json.loads(res.text))

    def _get_sha512(self) -> str:
        info("Calculating SHA512...")
        portfile = cast(Portfile, self._portfile)
        uri = f"https://github.com/{portfile.repo}/archive/{self._latest_ref}.tar.gz"
        res = requests.get(uri, proxies=self._proxy)
        if res.status_code != 200:
            error("Failed to fetch archive, status code {}", res.status_code)
        digest = hashlib.sha512(res.content).hexdigest()
        info("Archive SHA512 digest: {}", digest)
        return digest

    def _amend_commit(self) -> None:
        self._repo.git.commit("--amend", "--no-edit")

    def _update_port(self):
        info("Updating versions...")
        portfile = cast(Portfile, self._portfile)
        portfile.ref = self._latest_ref
        portfile.sha512 = self._get_sha512()
        portfile.save()
        manifest = cast(Manifest, self._manifest)
        port_dir = self._config.ports_path / "ports" / self._config.name
        manifest_path = port_dir / "vcpkg.json"
        manifest.write(manifest_path)
        self._repo.index.add([str(portfile.path.resolve()), str(manifest_path.resolve())])
        if self._config.fix:
            self._amend_commit()
        else:
            self._repo.index.commit(f"Updated {self._config.name} to {manifest.version_repr}")

    def _update_versions(self):
        info("Updating version file...")
        manifest = cast(Manifest, self._manifest)
        obj = str(self._repo.rev_parse(f"HEAD:ports/{self._config.name}"))
        info("Latest ports commit object: {}", obj)
        initial = self._config.name[0] + '-'
        version_path = self._config.ports_path / "versions" / initial / f"{self._config.name}.json"
        versions: List = json.loads(version_path.read_text()).get("versions", [])

        def fix_front_version():
            if not versions:
                return False
            front = versions[0]
            return (front.get(manifest.version_type) == manifest.version and
                    front.get("port-version", 0) == manifest.port_version)

        if fix_front_version():
            versions[0]["git-tree"] = obj
        else:
            versions.insert(0, {
                manifest.version_type: manifest.version,
                "port-version": manifest.port_version,
                "git-tree": obj
            })
        version_path.write_text(json.dumps({"versions": versions}, indent=4))

        info("Updating baseline...")
        baseline_path = self._config.ports_path / "versions" / "baseline.json"
        baseline = json.loads(baseline_path.read_text())
        baseline["default"][self._config.name] = {
            "baseline": manifest.version,
            "port-version": manifest.port_version
        }
        baseline_path.write_text(json.dumps(baseline, indent=4))

        self._repo.index.add([str(version_path.resolve()), str(baseline_path.resolve())])
        self._amend_commit()

    def _get_vcpkg_config(self):
        info("Fetching registry configurations...")
        portfile = cast(Portfile, self._portfile)
        uri = (f"https://raw.githubusercontent.com/{portfile.repo}/{self._latest_ref}" +
               "/vcpkg-configuration.json")
        res = requests.get(uri, proxies=self._proxy)
        if res.status_code == 404:
            info("No registry configuration found, using defaults...")
            return None
        if res.status_code != 200:
            error("Failed to fetch manifest, status code {}", res.status_code)
        return json.loads(res.text)

    def _setup_test(self):
        info("Setting up installation test...")
        test_path = self._config.ports_path / "temp" / "install-test"
        if not test_path.exists():
            test_path.mkdir(parents=True)

        (test_path / "vcpkg.json").write_text(json.dumps({
            "name": "vcpkg-ports-test",
            "version-string": "0.0.1",
            "dependencies": [self._config.name]
        }, indent=4))

        vcpkg_config = {
            "registries": [{
                "kind": "git",
                "repository": "file:///" + str(self._config.ports_path.absolute()),
                "packages": [self._config.name],
                "baseline": str(self._repo.rev_parse("HEAD"))
            }],
            "default-registry": {
                "kind": "git",
                "repository": "https://github.com/microsoft/vcpkg",
                "baseline": self._vcpkg_latest_ref
            }
        }
        port_vcpkg_config = self._get_vcpkg_config()
        if port_vcpkg_config:
            if "registries" in port_vcpkg_config:
                vcpkg_config["registries"].extend(port_vcpkg_config["registries"])

        vcpkg_config_path = test_path / "vcpkg-configuration.json"
        vcpkg_config_path.write_text(json.dumps(vcpkg_config, indent=4))

        vcpkg_installed_path = test_path / "vcpkg_installed"
        if vcpkg_installed_path.exists():
            shutil.rmtree(vcpkg_installed_path)

    def _test_install(self):
        info("Testing installation...")
        original = os.getcwd()
        os.chdir(str(self._config.ports_path / "temp" / "install-test"))
        try:
            sp.check_call(["vcpkg", "install"])
        except sp.CalledProcessError:
            error("Installation test failed, and the fix cannot be done automatically")
        finally:
            os.chdir(original)

    def _push_remote(self):
        if not self._config.push:
            return
        info("Pushing ports to remote repo...")
        self._repo.git.push()
