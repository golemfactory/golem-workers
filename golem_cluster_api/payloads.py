import base64
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

import aiohttp
from golem.payload import (
    Constraints,
    ManifestVmPayload,
    NodeInfo,
    Payload,
    Properties,
    RepositoryVmPayload,
    constraint,
    defaults,
)
from pydantic import AnyUrl
from yarl import URL

from golem_cluster_api.exceptions import ClusterApiError, RegistryRequestError

logger = logging.getLogger(__name__)


def get_manifest(
    image_url: Optional[URL],
    image_hash: Optional[str],
    protocols: List[str],
    outbound_urls: List[str],
) -> Dict:
    manifest = {
        "version": "0.1.0",
        "createdAt": "2023-06-26T00:00:00.000000Z",
        "expiresAt": "2100-01-01T00:00:00.000000Z",
        "metadata": {
            "name": "Cluster Api",
            "description": "Cluster Api",
            "version": "0.0.1",
        },
        "payload": [],
        "compManifest": {
            "version": "0.1.0",
            "script": {
                "commands": [
                    "run /bin/sh -c *",
                ],
                "match": "regex",
            },
            "net": {
                "inet": {
                    "out": {
                        "protocols": protocols,
                        "urls": outbound_urls,
                    }
                }
            },
        },
    }

    if image_url and image_hash:
        manifest["payload"] = [
            {
                "urls": [str(image_url)],
                "hash": f"sha3:{image_hash}",
            }
        ]

    logger.debug(f"Manifest generated: {manifest}")
    return manifest


@dataclass
class MaxCpuThreadsPayload(Payload):
    max_cpu_threads: int = constraint(defaults.PROP_INF_CPU_THREADS, "<=", default=None)


@dataclass
class ClusterNodePayload(Payload):
    image_hash: Optional[str] = None
    image_tag: Optional[str] = None
    capabilities: List[str] = field(default_factory=lambda: ["vpn", "inet"])
    outbound_urls: List[AnyUrl] = field(default_factory=list)
    min_mem_gib: Optional[float] = None
    min_cpu_threads: Optional[int] = None
    min_storage_gib: Optional[float] = None
    max_cpu_threads: Optional[int] = None
    runtime: str = "vm"
    registry_stats: bool = True
    subnet_tag: str = "public"

    async def build_properties_and_constraints(self) -> Tuple[Properties, Constraints]:
        payloads = await self.get_payloads_from_demand_config()

        properties = Properties()
        constraints = Constraints()

        for payload in payloads:
            ps, cs = await payload.build_properties_and_constraints()
            properties.update(ps)
            constraints.items.append(cs)

        return properties, constraints

    async def get_payloads_from_demand_config(self) -> List[Payload]:
        image_url, image_hash = await self._get_image_url_and_hash()
        max_cpu_payload = MaxCpuThreadsPayload(
            max_cpu_threads=self.max_cpu_threads,
        )

        if not self.outbound_urls:
            return [
                max_cpu_payload,
                NodeInfo(subnet_tag=self.subnet_tag),
                await self._get_repository_payload(image_url, image_hash),
            ]

        if "manifest-support" not in self.capabilities:
            self.capabilities.append("manifest-support")

        return [
            max_cpu_payload,
            NodeInfo(subnet_tag=self.subnet_tag),
            await self._get_manifest_payload(image_url, image_hash),
        ]

    async def _get_repository_payload(
        self, image_url: Optional[URL], image_hash: Optional[str]
    ) -> Payload:
        params = {
            k: v
            for k, v in asdict(self).items()
            if k
            not in {
                "image_hash",
                "image_tag",
                "outbound_urls",
                "subnet_tag",
                "max_cpu_threads",
                "registry_stats",
            }
        }

        params["image_hash"] = image_hash
        params["image_url"] = image_url
        return RepositoryVmPayload(**params)

    async def _get_manifest_payload(
        self, image_url: Optional[URL], image_hash: Optional[str]
    ) -> Payload:
        manifest = get_manifest(
            image_url,
            image_hash,
            list(set([URL(url).scheme for url in self.outbound_urls])),
            self.outbound_urls,
        )
        logger.debug("Generated manifest:  %s", str(manifest))
        manifest = base64.b64encode(json.dumps(manifest).encode("utf-8")).decode("utf-8")

        params = {
            k: v
            for k, v in asdict(self).items()
            if k
            not in {
                "image_hash",
                "image_tag",
                "outbound_urls",
                "subnet_tag",
                "max_cpu_threads",
                "registry_stats",
            }
        }

        params["manifest"] = manifest
        return ManifestVmPayload(**params)

    async def _get_image_url_and_hash(self) -> Tuple[Optional[URL], Optional[str]]:
        if self.image_tag is not None and self.image_hash is not None:
            raise ClusterApiError("Either the `image_tag` or `image_hash` is allowed, not both.")

        if self.image_hash is not None:
            image_url = await self._get_image_url_from_hash(self.image_hash)
            return image_url, self.image_hash

        if self.image_tag is not None:
            return await self._get_image_url_and_hash_from_tag(self.image_tag)

        return None, None

    async def _get_image_url_from_hash(self, image_hash: str) -> URL:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://registry.golem.network/v1/image/info",
                params={"hash": image_hash, "count": str(self.registry_stats).lower()},
            ) as response:
                response_data = await response.json()

                if response.status == 200:
                    return URL(response_data["http"])
                elif response.status == 404:
                    raise RegistryRequestError(f"Image hash `{image_hash}` does not exist")
                else:
                    raise RegistryRequestError("Can't access Golem Registry for image lookup!")

    async def _get_image_url_and_hash_from_tag(self, image_tag: str) -> Tuple[URL, str]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://registry.golem.network/v1/image/info",
                params={"tag": image_tag, "count": str(self.registry_stats).lower()},
            ) as response:
                response_data = await response.json()

                if response.status == 200:
                    return response_data["http"], response_data["sha3"]
                elif response.status == 404:
                    raise RegistryRequestError(f"Image tag `{image_tag}` does not exist")
                else:
                    raise RegistryRequestError("Can't access Golem Registry for image lookup!")
