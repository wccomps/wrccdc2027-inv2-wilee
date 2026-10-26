<?php
// Usage: php dbcheck.php <creds.json> <host> <port> <dbname>
// Prints "present" if Roundcube's schema exists, "missing" otherwise.
$c = json_decode(file_get_contents($argv[1]), true);
$pdo = new PDO("mysql:host={$argv[2]};port={$argv[3]};dbname={$argv[4]}", $c['username'], $c['password']);
echo $pdo->query("SHOW TABLES LIKE 'system'")->rowCount() ? "present" : "missing";
