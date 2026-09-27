package com.yojnasetu;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Bean;
import org.testcontainers.mongodb.MongoDBAtlasLocalContainer;
import org.testcontainers.utility.DockerImageName;

@TestConfiguration(proxyBeanMethods = false)
class TestcontainersConfiguration {

	// Same image as local development (docker-compose.yml) so tests exercise the same server.
	@Bean
	@ServiceConnection
	MongoDBAtlasLocalContainer mongoDbContainer() {
		return new MongoDBAtlasLocalContainer(DockerImageName.parse("mongodb/mongodb-atlas-local:8.0"));
	}

}
