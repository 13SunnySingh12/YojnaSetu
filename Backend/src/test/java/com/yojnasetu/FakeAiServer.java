package com.yojnasetu;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

import com.sun.net.httpserver.HttpServer;

/**
 * MOCK / TEST ONLY: stands in for the FastAPI AI service. Unconfigured paths answer 503, so every test
 * exercises the "AI unavailable" path unless it opts in with {@link #respond}.
 */
public final class FakeAiServer {

	public record Recorded(String path, String token, String body) {
	}

	private record Reply(int status, String json) {
	}

	private static final Map<String, Reply> replies = new ConcurrentHashMap<>();

	private static final List<Recorded> requests = new CopyOnWriteArrayList<>();

	private static final HttpServer server = start();

	private FakeAiServer() {
	}

	public static String url() {
		return "http://127.0.0.1:" + server.getAddress().getPort();
	}

	public static void respond(String path, String json) {
		replies.put(path, new Reply(200, json));
	}

	public static void respond(String path, int status, String json) {
		replies.put(path, new Reply(status, json));
	}

	public static List<Recorded> requests() {
		return List.copyOf(requests);
	}

	public static void reset() {
		replies.clear();
		requests.clear();
	}

	private static HttpServer start() {
		try {
			HttpServer http = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
			http.createContext("/", exchange -> {
				try (InputStream in = exchange.getRequestBody(); OutputStream out = exchange.getResponseBody()) {
					String path = exchange.getRequestURI().getPath();
					requests.add(new Recorded(path, exchange.getRequestHeaders().getFirst("X-Internal-Token"),
							new String(in.readAllBytes(), StandardCharsets.UTF_8)));
					Reply reply = replies.getOrDefault(path, new Reply(503, "{\"detail\":\"AI provider unavailable\"}"));
					byte[] body = reply.json().getBytes(StandardCharsets.UTF_8);
					exchange.getResponseHeaders().add("Content-Type", "application/json");
					exchange.sendResponseHeaders(reply.status(), body.length);
					out.write(body);
				}
			});
			http.start();
			return http;
		}
		catch (IOException ex) {
			throw new IllegalStateException("could not start the fake AI server", ex);
		}
	}

}
