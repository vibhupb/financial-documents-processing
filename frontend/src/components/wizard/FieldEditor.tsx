import { X, GripVertical, Plus } from 'lucide-react';

export interface FieldDef {
  name: string;
  label: string;
  type: 'string' | 'number' | 'date' | 'boolean' | 'currency';
  query: string;
  formKey?: string;
}

interface FieldEditorProps {
  fields: FieldDef[];
  onChange: (fields: FieldDef[]) => void;
  formKeys?: Record<string, { value: string; confidence: number }>;
}

const fieldTypes = ['string', 'number', 'date', 'boolean', 'currency'] as const;

export default function FieldEditor({ fields, onChange, formKeys }: FieldEditorProps) {
  function updateField(index: number, patch: Partial<FieldDef>) {
    const updated = fields.map((f, i) => (i === index ? { ...f, ...patch } : f));
    onChange(updated);
  }

  function removeField(index: number) {
    onChange(fields.filter((_, i) => i !== index));
  }

  function addField() {
    onChange([
      ...fields,
      { name: '', label: '', type: 'string', query: '' },
    ]);
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-12 gap-2 text-xs font-medium text-gray-500 px-1">
        <div className="col-span-1" />
        <div className="col-span-2">Field Name</div>
        <div className="col-span-2">Label</div>
        <div className="col-span-1">Type</div>
        <div className="col-span-3">Textract Query</div>
        <div className="col-span-2">Form Key</div>
        <div className="col-span-1" />
      </div>

      {fields.map((field, i) => (
        <div
          key={i}
          className="grid grid-cols-12 gap-2 items-center bg-white border border-gray-200 rounded-lg p-2"
        >
          <div className="col-span-1 flex justify-center text-gray-300">
            <GripVertical className="w-4 h-4" />
          </div>
          <input
            className="col-span-2 px-2 py-1.5 text-sm border border-gray-200 rounded focus:border-primary-400 focus:outline-none"
            placeholder="fieldName"
            value={field.name}
            onChange={(e) => updateField(i, { name: e.target.value })}
          />
          <input
            className="col-span-2 px-2 py-1.5 text-sm border border-gray-200 rounded focus:border-primary-400 focus:outline-none"
            placeholder="Display Label"
            value={field.label}
            onChange={(e) => updateField(i, { label: e.target.value })}
          />
          <select
            className="col-span-1 px-1 py-1.5 text-sm border border-gray-200 rounded focus:border-primary-400 focus:outline-none bg-white"
            value={field.type}
            onChange={(e) => updateField(i, { type: e.target.value as FieldDef['type'] })}
          >
            {fieldTypes.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <input
            className="col-span-3 px-2 py-1.5 text-sm border border-gray-200 rounded focus:border-primary-400 focus:outline-none"
            placeholder="What is the interest rate?"
            value={field.query}
            onChange={(e) => updateField(i, { query: e.target.value })}
          />
          <select
            className="col-span-2 px-1 py-1.5 text-sm border border-gray-200 rounded focus:border-primary-400 focus:outline-none bg-white"
            value={field.formKey || ''}
            onChange={(e) => updateField(i, { formKey: e.target.value || undefined })}
          >
            <option value="">-- none --</option>
            {formKeys &&
              Object.keys(formKeys).map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
          </select>
          <button
            onClick={() => removeField(i)}
            className="col-span-1 flex justify-center text-gray-400 hover:text-red-500"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}

      <button
        onClick={addField}
        className="flex items-center gap-1.5 text-sm text-primary-600 hover:text-primary-700 font-medium mt-2"
      >
        <Plus className="w-4 h-4" /> Add Field
      </button>
    </div>
  );
}
