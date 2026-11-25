<script setup>
import { formatDecimal } from '@/lib/numberFormat.js'
import { ref } from 'vue'
import { Button } from '@/components/ui/button'

defineProps({ lines: { type: Array, default: () => [] } })
const copied = ref('')
const labels = {
  511: 'Security',
  512: 'Sale date',
  514: 'Unit selling price (EUR)',
  515: 'Shares sold',
  516: 'Gross proceeds (EUR)',
  517: 'Selling fees (EUR)',
  518: 'Net proceeds (EUR)',
  520: 'Unit acquisition FMV (EUR)',
  521: 'Acquisition total (EUR)',
  522: 'Acquisition fees (EUR)',
  523: 'Total acquisition basis (EUR)',
  524: 'Gain / loss (EUR)',
}
const copy = async (value, key) => {
  try {
    await navigator.clipboard.writeText(String(value))
    copied.value = key
  } catch {
    copied.value = 'Copy unavailable — select the value to copy it.'
  }
}
</script>

<template>
  <div class="space-y-3">
    <p class="text-sm text-muted-foreground">
      2074 · Déclaration des plus ou moins-values réalisées. Values are in EUR unless marked
      otherwise.
    </p>
    <p
      v-if="copied.startsWith('Copy unavailable')"
      role="status"
      class="text-sm text-muted-foreground"
    >
      {{ copied }}
    </p>
    <details
      v-for="(line, index) in lines"
      :key="`${line.sale_id}-${line.allocation_id}-${index}`"
      class="rounded-lg border p-3"
    >
      <summary class="cursor-pointer text-sm font-medium">
        {{ line.fields['511'] }} · {{ line.fields['512'] }} ·
        {{ formatDecimal(line.fields['515']) }} shares · gain/loss €{{
          formatDecimal(line.fields['524'])
        }}
      </summary>
      <p v-if="line.regime && Number(line.absorbed_loss) > 0" class="mt-3 text-sm">
        Loss adjustment: €{{ formatDecimal(line.absorbed_loss) }} of this disposal loss reduces the
        matching RSU acquisition gain. This allocation's ordinary capital contribution is €{{
          formatDecimal(line.contributions.capital_result)
        }}
        after that adjustment. The absorbed loss is counted once.
      </p>
      <div class="mt-3 overflow-x-auto">
        <table class="w-full min-w-[28rem] text-sm">
          <thead>
            <tr class="border-b text-left">
              <th class="p-2">Line</th>
              <th class="p-2">Field</th>
              <th class="p-2 text-right">Value</th>
              <th class="p-2">Copy</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(value, code) in line.fields" :key="code" class="border-b last:border-0">
              <td class="p-2">{{ code }}</td>
              <td class="p-2">{{ labels[code] }}</td>
              <td class="max-w-xs break-all p-2 text-right font-mono tabular-nums select-text">
                {{ ['511', '512'].includes(code) ? value : formatDecimal(value) }}
              </td>
              <td class="p-2">
                <Button
                  variant="ghost"
                  size="sm"
                  :aria-label="`Copy line ${code} for sale ${line.sale_id}, allocation ${line.allocation_id}`"
                  @click="copy(value, `${index}-${code}`)"
                  >{{ copied === `${index}-${code}` ? 'Copied' : 'Copy' }}</Button
                >
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <dl class="mt-4 grid gap-2 break-words text-xs sm:grid-cols-2">
        <div>
          <dt class="text-muted-foreground">Acquired</dt>
          <dd>
            {{ line.acquisition_date }} · {{ line.acquisition_type }} · lot
            {{ line.acquisition_id }}
          </dd>
        </div>
        <div>
          <dt class="text-muted-foreground">Original unit values</dt>
          <dd>
            Acquisition ${{ formatDecimal(line.acquisition_fmv_usd) }} · sale ${{
              formatDecimal(line.selling_price_usd)
            }}
            · fees ${{ formatDecimal(line.fees_usd) }}
          </dd>
        </div>
        <div
          v-for="(fx, kind) in { Acquisition: line.acquisition_fx, Sale: line.selling_fx }"
          :key="kind"
        >
          <dt class="text-muted-foreground">{{ kind }} conversion</dt>
          <dd>
            {{ fx.event_date }} → {{ fx.rate_date }} · {{ fx.source }} ·
            {{ formatDecimal(fx.rate) }}
            {{ fx.direction }}
          </dd>
        </div>
        <div v-if="line.acquisition_value_usd !== undefined">
          <dt class="text-muted-foreground">Acquisition conversion result</dt>
          <dd>
            ${{ formatDecimal(line.acquisition_value_usd) }} → €{{
              formatDecimal(line.acquisition_value_eur)
            }}
            before reporting-line rounding
          </dd>
        </div>
        <div v-if="line.proceeds_usd !== undefined">
          <dt class="text-muted-foreground">Sale conversion result</dt>
          <dd>
            ${{ formatDecimal(line.proceeds_usd) }} → €{{ formatDecimal(line.proceeds_eur) }} · fees
            ${{ formatDecimal(line.fees_usd) }} → €{{ formatDecimal(line.fees_eur) }}
            before reporting-line rounding
          </dd>
        </div>
        <template v-if="line.regime">
          <div>
            <dt class="text-muted-foreground">RSU regime and taxpayer</dt>
            <dd>
              {{ line.regime }} · {{ line.taxpayer_role }} · approval {{ line.approval_date }}
            </dd>
          </div>
          <div>
            <dt class="text-muted-foreground">Acquisition gain after loss adjustment</dt>
            <dd>
              €{{ formatDecimal(line.acquisition_gain) }} · absorbed loss €{{
                formatDecimal(line.absorbed_loss)
              }}
            </dd>
          </div>
          <div>
            <dt class="text-muted-foreground">Threshold allocation</dt>
            <dd>
              Eligible €{{ formatDecimal(line.threshold_eligible) }} · excess €{{
                formatDecimal(line.threshold_excess)
              }}
            </dd>
          </div>
          <div>
            <dt class="text-muted-foreground">Computed declaration contributions (EUR)</dt>
            <dd v-for="(value, code) in line.contributions" :key="code">
              {{ code }}: {{ formatDecimal(value) }}
            </dd>
          </div>
        </template>
      </dl>
    </details>
    <p v-if="!lines.length" class="text-sm text-muted-foreground">
      This manually entered source has no generated 2074 helper.
    </p>
  </div>
</template>
