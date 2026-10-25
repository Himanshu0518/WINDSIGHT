import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'

interface DeliveryDatePickerProps {
  value: string
  onChange: (value: string) => void
  /** Inclusive bounds from /health; omitted while unknown. */
  min?: string | null
  max?: string | null
}

/** Delivery-day selector constrained to the period covered by the dataset. */
export function DeliveryDatePicker({ value, onChange, min, max }: DeliveryDatePickerProps) {
  return (
    <div className="flex items-center gap-2">
      <Label
        htmlFor="delivery-date"
        className="text-xs text-muted-foreground whitespace-nowrap"
      >
        Delivery date
      </Label>
      <Input
        id="delivery-date"
        type="date"
        value={value}
        min={min ?? undefined}
        max={max ?? undefined}
        onChange={(event) => {
          if (event.target.value) onChange(event.target.value)
        }}
        className="h-9 w-[150px] tabular-nums"
      />
    </div>
  )
}
