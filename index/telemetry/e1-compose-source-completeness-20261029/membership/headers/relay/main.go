/*
   Copyright 2020 Docker Compose CLI authors

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
*/

// compose-relay is the network gateway Docker Compose deploys in place of a
// provider-managed service. It joins the project networks under the service's
// name and forwards each declared container port to the endpoint the provider
// published (typically a port on the host gateway), so consumers keep using
// the compose-native address (http://<service>:<port>) for a resource that
// lives outside the compose network.
//
// Routes come from the RELAY_ROUTES environment variable:
//
//	RELAY_ROUTES=80=host.docker.internal:49152,9000=host.docker.internal:30001
//
// One listener per route, TCP only.
package main
