/**
 * Sentinel — Demo Payloads
 * Pre-filled payloads matching the backend's demo mode data contracts.
 */

export const demoImpactPayload = {
  project_id: 'demo-project',
  change: {
    file: 'cart.py',
    start_line: 42,
    end_line: 48,
    symbol: 'calculate_total',
    change_type: 'RETURN_TYPE_CHANGE',
    description: 'Return type changed from dictionary to CartTotal',
    before: "return {'subtotal': subtotal, 'tax': tax}",
    after: 'return CartTotal(subtotal, tax)',
  },
  impacted_components: [
    {
      file: 'payment.py',
      start_line: 87,
      end_line: 90,
      symbol: 'process_payment',
      relationship: 'calls',
    },
  ],
  impact_chain: [
    'cart.py:calculate_total',
    'payment.py:process_payment',
    'checkout.py:checkout',
  ],
  evidence: [
    {
      file: 'cart.py',
      start_line: 42,
      end_line: 48,
      content:
        'def calculate_total(cart):\n    subtotal = sum(item.price * item.qty for item in cart.items)\n    tax = subtotal * cart.tax_rate\n    return CartTotal(subtotal, tax)\n',
    },
    {
      file: 'payment.py',
      start_line: 87,
      end_line: 90,
      content:
        "    total = calculate_total(cart)\n    tax = total['tax']\n",
    },
  ],
};

export const demoAskPayload = {
  question: "Why does payment.py break after the cart.py change?",
  project_id: 'demo-project',
  impact_context: demoImpactPayload,
  evidence: demoImpactPayload.evidence,
  constraints: [],
};

export const demoFixPayload = {
  instruction: "Update payment.py to use attribute access instead of dictionary subscript for the CartTotal return type.",
  constraints: ['Preserve existing behavior', 'Do not modify public API'],
  impact_analysis: {
    ...demoImpactPayload,
    evidence: [
      ...demoImpactPayload.evidence,
      {
        file: 'cart.py',
        start_line: 1,
        end_line: 10,
        content: 'class CartTotal:\n    def __init__(self, subtotal, tax):\n        self.subtotal = subtotal\n        self.tax = tax\n',
      },
    ],
  },
  evidence: [
    ...demoImpactPayload.evidence,
    {
      file: 'cart.py',
      start_line: 1,
      end_line: 10,
      content: 'class CartTotal:\n    def __init__(self, subtotal, tax):\n        self.subtotal = subtotal\n        self.tax = tax\n',
    },
  ],
  target_file: 'payment.py',
};

export const demoValidatePayload = {
  original_analysis: demoImpactPayload,
  new_evidence: [
    {
      file: 'payment.py',
      start_line: 87,
      end_line: 90,
      content: '    total = calculate_total(cart)\n    tax = total.tax\n',
    },
  ],
  test_results: { passed: true },
};
