<?php

namespace App\Console\Commands;

use Illuminate\Console\Command;
use Illuminate\Support\Facades\Schema;

class ReportTables extends Command
{
    protected $signature = 'payroll:report-tables';

    protected $description = 'List every table in the payroll database';

    public function handle(): int
    {
        $tables = Schema::getTableListing();

        foreach ($tables as $table) {
            $this->line($table);
        }

        $views = Schema::getViews();

        $this->info(sprintf('Tables: %d, Views: %d', count($tables), count($views)));

        return self::SUCCESS;
    }
}
