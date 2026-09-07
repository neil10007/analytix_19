# -*- coding: utf-8 -*-
{
    'name': 'Chatting AI',
    'version': '1.0',
    'category': 'Productivity',
    'author': 'Analytix',
    'summary': 'AI Chat Interface',
    'description': """
        Adds a floating button in Odoo that opens an AI chat window.
    """,
    'depends': ['base', 'web'],
    'data': [
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'chatting_ai/static/src/components/ai_chat/ai_chat.scss',
            'chatting_ai/static/src/components/ai_chat/ai_chat.xml',
            'chatting_ai/static/src/components/ai_chat/ai_chat.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
