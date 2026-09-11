package com.kyzer.downloader;

import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.regex.Pattern;

@RestController
public class DownloaderController {
    private final Path downloadDir = Paths.get(System.getProperty("java.io.tmpdir"), "kyzer-downloads");
    private static final Pattern SAFE_URL = Pattern.compile("^https?://(www\\.)?(youtube\\.com|youtu\\.be)/.*$", Pattern.CASE_INSENSITIVE);

    public DownloaderController() throws IOException {
        Files.createDirectories(downloadDir);
    }

    @GetMapping(value = "/", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> home() throws IOException {
        Path index = Paths.get("src/main/resources/static/index.html");
        if (Files.exists(index)) return ResponseEntity.ok(Files.readString(index));
        return ResponseEntity.ok("<h1>KyZer Video Downloader</h1>");
    }

    @GetMapping("/health")
    public Map<String, String> health() { return Map.of("status", "ok"); }

    @PostMapping("/api/info")
    public ResponseEntity<?> info(@RequestBody Map<String, String> body) {
        String url = body.getOrDefault("url", "").trim();
        if (!valid(url)) return ResponseEntity.badRequest().body(Map.of("error", "Please enter a valid YouTube URL."));
        try {
            List<String> cmd = List.of("yt-dlp", "--dump-single-json", "--no-playlist", "--quiet", url);
            Process p = new ProcessBuilder(cmd).redirectErrorStream(true).start();
            String output = read(p);
            int exit = p.waitFor();
            if (exit != 0) return ResponseEntity.internalServerError().body(Map.of("error", output));
            return ResponseEntity.ok(parseInfo(output));
        } catch (Exception e) {
            return ResponseEntity.internalServerError().body(Map.of("error", e.getMessage()));
        }
    }

    @PostMapping("/api/download")
    public ResponseEntity<?> download(@RequestBody Map<String, String> body) {
        String url = body.getOrDefault("url", "").trim();
        String quality = body.getOrDefault("quality", "best").trim();
        if (!valid(url)) return ResponseEntity.badRequest().body(Map.of("error", "Please enter a valid YouTube URL."));
        if (!quality.equals("best") && !quality.equals("worst") && !quality.matches("\\d+"))
            return ResponseEntity.badRequest().body(Map.of("error", "Invalid quality."));

        String id = UUID.randomUUID().toString().replace("-", "");
        String template = downloadDir.resolve(id + ".%(ext)s").toString();
        String format = quality.equals("best") ? "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                : quality.equals("worst") ? "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst"
                : quality + "+bestaudio/best";

        try {
            List<String> cmd = new ArrayList<>(List.of("yt-dlp", "--no-playlist", "--format", format,
                    "--merge-output-format", "mp4", "--output", template, url));
            Process p = new ProcessBuilder(cmd).redirectErrorStream(true).start();
            String output = read(p);
            int exit = p.waitFor();
            if (exit != 0) return ResponseEntity.internalServerError().body(Map.of("error", output));

            try (DirectoryStream<Path> files = Files.newDirectoryStream(downloadDir, id + ".*")) {
                for (Path file : files) {
                    if (!Files.isRegularFile(file)) continue;
                    String name = file.getFileName().toString();
                    String extension = name.contains(".") ? name.substring(name.lastIndexOf('.')) : ".mp4";
                    return ResponseEntity.ok()
                            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"kyzer-video" + extension + "\"")
                            .contentType(MediaType.parseMediaType("video/mp4"))
                            .body(new FileSystemResource(file));
                }
            }
            return ResponseEntity.internalServerError().body(Map.of("error", "Output file was not found."));
        } catch (Exception e) {
            return ResponseEntity.internalServerError().body(Map.of("error", e.getMessage()));
        }
    }

    private boolean valid(String url) { return SAFE_URL.matcher(url).matches(); }

    private String read(Process p) throws IOException {
        try (BufferedReader r = p.inputReader()) {
            return r.lines().reduce("", (a, b) -> a + b + "\n");
        }
    }

    private Map<String, Object> parseInfo(String json) {
        String title = extract(json, "title");
        String thumbnail = extract(json, "thumbnail");
        String duration = extract(json, "duration");
        return Map.of("title", title, "thumbnail", thumbnail, "duration", duration);
    }

    private String extract(String json, String key) {
        String marker = "\"" + key + "\":";
        int start = json.indexOf(marker);
        if (start < 0) return "";
        start += marker.length();
        while (start < json.length() && Character.isWhitespace(json.charAt(start))) start++;
        if (start < json.length() && json.charAt(start) == '"') {
            int end = start + 1;
            while (end < json.length()) {
                if (json.charAt(end) == '"' && json.charAt(end - 1) != '\\') break;
                end++;
            }
            return json.substring(start + 1, Math.min(end, json.length())).replace("\\\"", "\"");
        }
        int end = start;
        while (end < json.length() && ",}".indexOf(json.charAt(end)) < 0) end++;
        return json.substring(start, end).trim();
    }
}
