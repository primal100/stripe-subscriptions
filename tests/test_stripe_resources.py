import pytest
import stripe

import subscriptions


@pytest.mark.parametrize('options, expected', [
    ({}, {}),
    ({'payment_method_types': ['card']}, {'allowed_payment_method_types': ['card']}),
    ({'allowed_payment_method_types': ['card']}, {'allowed_payment_method_types': ['card']}),
])
def test_setup_intent_payment_method_parameters(monkeypatch, options, expected):
    from unittest.mock import Mock

    intent = stripe.SetupIntent.construct_from({'id': 'seti_test'}, None)
    create = Mock(return_value=intent)
    monkeypatch.setattr(stripe.SetupIntent, 'create', create)
    user = subscriptions.User(1, 'test@example.com', 'cus_test')
    assert subscriptions.create_setup_intent(user, metadata={'test': 'value'}, **options) is intent
    create.assert_called_once_with(
        customer='cus_test', confirm=False, usage='off_session', metadata={'test': 'value'}, **expected
    )


def test_setup_intent_rejects_conflicting_method_arguments(monkeypatch):
    from unittest.mock import Mock

    create = Mock()
    monkeypatch.setattr(stripe.SetupIntent, 'create', create)
    with pytest.raises(TypeError, match='not both'):
        subscriptions.create_setup_intent(
            subscriptions.User(1, 'test@example.com', 'cus_test'),
            payment_method_types=['card'], allowed_payment_method_types=['sepa_debit'],
        )
    create.assert_not_called()


@pytest.mark.parametrize('as_resource', [False, True])
@pytest.mark.parametrize('plan', [None, {}, {'id': 'price_test', 'product': 'prod_test'}])
def test_subscription_summary(monkeypatch, as_resource, plan):
    data = {'id': 'sub_test', 'plan': plan}
    sub = stripe.Subscription.construct_from(data, None) if as_resource else data
    monkeypatch.setattr(subscriptions, 'list_active_subscriptions', lambda *a, **kw: [sub])

    assert subscriptions._check_subscription_product_id(sub) == (plan or {}).get('product')
    assert subscriptions._check_subscription_price_id(sub) == (plan or {}).get('id')
    assert subscriptions.list_products_prices_subscribed_to(None) == [{
        'sub_id': 'sub_test', 'product_id': (plan or {}).get('product'),
        'price_id': (plan or {}).get('id'), 'cancel_at': None, 'current_period_end': None,
    }]


def test_subscription_summary_preserves_dates(monkeypatch):
    sub = stripe.Subscription.construct_from({
        'id': 'sub_test', 'cancel_at': 100, 'current_period_end': 200,
    }, None)
    monkeypatch.setattr(subscriptions, 'list_active_subscriptions', lambda *a, **kw: [sub])
    result = subscriptions.list_products_prices_subscribed_to(None)[0]
    assert result['cancel_at'] == 100
    assert result['current_period_end'] == 200


@pytest.mark.parametrize('as_resource', [False, True])
def test_subscription_summary_uses_each_items_billing_period(monkeypatch, as_resource):
    data = {
        'id': 'sub_test', 'cancel_at': None,
        'items': {'object': 'list', 'data': [
            {'id': 'si_monthly', 'object': 'subscription_item', 'current_period_end': 200,
             'price': {'id': 'price_monthly', 'product': 'prod_monthly'}},
            {'id': 'si_yearly', 'object': 'subscription_item', 'current_period_end': 300,
             'price': {'id': 'price_yearly', 'product': {'id': 'prod_yearly'}}},
        ]},
    }
    sub = stripe.Subscription.construct_from(data, None) if as_resource else data
    monkeypatch.setattr(subscriptions, 'list_active_subscriptions', lambda *a, **kw: [sub])
    assert subscriptions.list_products_prices_subscribed_to(None) == [
        {'sub_id': 'sub_test', 'product_id': 'prod_monthly', 'price_id': 'price_monthly',
         'cancel_at': None, 'current_period_end': 200},
        {'sub_id': 'sub_test', 'product_id': 'prod_yearly', 'price_id': 'price_yearly',
         'cancel_at': None, 'current_period_end': 300},
    ]
    assert subscriptions.is_subscribed_and_cancelled_time(
        None, price_id='price_yearly'
    )['current_period_end'] == 300


@pytest.mark.parametrize('kind, minimize, data', [
    (stripe.Price, subscriptions._minimize_price, {
        'id': 'price_test', 'recurring': {'interval': 'month'}, 'type': 'recurring',
        'currency': 'usd', 'unit_amount': 100, 'unit_amount_decimal': '100',
        'nickname': None, 'product': 'prod_test', 'metadata': {'label': 'test'},
    }),
    (stripe.Product, subscriptions._minimize_product, {
        'id': 'prod_test', 'images': [], 'type': 'service', 'name': 'Test',
        'shippable': None, 'unit_label': None, 'url': None, 'metadata': {'label': 'test'},
    }),
])
def test_catalog_results_contain_plain_nested_dicts(kind, minimize, data):
    resource = kind.construct_from(data, None)
    result = minimize(resource)
    assert result == data
    assert isinstance(result['metadata'], dict)
    result['metadata']['label'] = 'changed'
    assert resource['metadata']['label'] == 'test'


def test_catalog_subscription_return_shapes(monkeypatch):
    price = {
        'id': 'price_test', 'recurring': {'interval': 'month'}, 'type': 'recurring',
        'currency': 'usd', 'unit_amount': 100, 'unit_amount_decimal': '100',
        'nickname': None, 'product': 'prod_test', 'metadata': {},
    }
    product = {
        'id': 'prod_test', 'images': [], 'type': 'service', 'name': 'Test',
        'shippable': None, 'unit_label': None, 'url': None, 'metadata': {},
    }
    info = {'sub_id': 'sub_test', 'cancel_at': None, 'current_period_end': 200}
    monkeypatch.setattr(subscriptions, 'get_active_prices', lambda **kw: [price])
    monkeypatch.setattr(subscriptions, 'get_active_products', lambda **kw: [product])
    monkeypatch.setattr(subscriptions, 'list_products_prices_subscribed_to', lambda *a, **kw: [
        {**info, 'product_id': 'prod_test', 'price_id': 'price_test'},
    ])
    monkeypatch.setattr(stripe.Price, 'retrieve', lambda *a, **kw: stripe.Price.construct_from(price, None))
    monkeypatch.setattr(stripe.Product, 'retrieve', lambda *a, **kw: stripe.Product.construct_from(product, None))

    expected_price = {**price, 'subscription_info': info}
    assert subscriptions.get_subscription_prices() == [expected_price]
    assert subscriptions.retrieve_price(None, 'price_test') == expected_price
    nested_price = {k: v for k, v in expected_price.items() if k != 'product'}
    expected_product = {**product, 'prices': [nested_price], 'subscription_info': info}
    assert subscriptions.get_subscription_products_and_prices() == [expected_product]
    assert subscriptions.retrieve_product(None, 'prod_test') == expected_product
    assert 'subscription_info' not in price
    assert 'prices' not in product


def test_cancel_subscription_checks_ownership(monkeypatch):
    from unittest.mock import Mock

    sub = stripe.Subscription.construct_from({'id': 'sub_test', 'object': 'subscription', 'customer': 'cus_owner'}, None)
    monkeypatch.setattr(stripe.Subscription, 'retrieve', lambda *a, **kw: sub)
    cancel = Mock(return_value=sub)
    monkeypatch.setattr(stripe.Subscription, 'cancel', cancel)
    with pytest.raises(subscriptions.StripeWrongCustomer):
        subscriptions.cancel_subscription(subscriptions.User(1, 'test@example.com', 'cus_other'), 'sub_test')
    cancel.assert_not_called()
    assert subscriptions.cancel_subscription(subscriptions.User(1, 'test@example.com', 'cus_owner'), 'sub_test') is sub
    cancel.assert_called_once_with('sub_test')
