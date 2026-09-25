<?php

namespace App\Support;

use Illuminate\Database\Schema\Blueprint;
use Illuminate\Database\Schema\Grammars\MySqlGrammar;
use Illuminate\Support\Facades\DB;

class PayrollSchema
{
    public static function addOvertimeRate(): void
    {
        $blueprint = new Blueprint('shifts');

        $blueprint->decimal('overtime_rate', 6, 4)->default(1.0);

        $blueprint->create();

        DB::table('shifts')->update(['overtime_rate' => 1.0]);
    }

    public static function dropLegacyColumn(string $column): void
    {
        $grammar = new MySqlGrammar();

        $grammar->setConnection(DB::connection());

        $blueprint = new Blueprint('shifts');

        $blueprint->dropColumn($column);

        $blueprint->create();
    }
}
